"""
Binance REST API client with proper authentication and rate limiting.
Implements all necessary endpoints for trading operations.
"""

import asyncio
import hashlib
import hmac
import json
import time
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlencode
import aiohttp
import logging

from ..types import Order, OrderSide, OrderType, TimeInForce, OrderStatus, AccountInfo, ExchangeInfo
from .rate_limiter import RateLimiter, RateLimit


class BinanceRESTClient:
    """
    Binance REST API client with authentication and rate limiting.
    
    Handles all REST API calls to Binance including:
    - Account information
    - Order placement and management
    - Market data (as fallback)
    - Exchange information
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://api.binance.com",
        testnet: bool = False
    ):
        """
        Initialize Binance REST client.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            base_url: Base URL for API calls
            testnet: Whether to use testnet
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip('/')
        self.testnet = testnet
        
        self.logger = logging.getLogger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limiter = RateLimiter()
        
        # Exchange info cache
        self.exchange_info: Optional[ExchangeInfo] = None
        self.exchange_info_updated = 0
        self.exchange_info_ttl = 3600  # 1 hour
    
    async def initialize(self) -> None:
        """Initialize the client and load exchange information."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'X-MBX-APIKEY': self.api_key,
                'Content-Type': 'application/json',
            }
        )
        
        # Load exchange information
        await self._load_exchange_info()
    
    async def close(self) -> None:
        """Close the client session."""
        if self.session:
            await self.session.close()
    
    async def _load_exchange_info(self) -> None:
        """Load exchange information and update rate limits."""
        try:
            exchange_info = await self.get_exchange_info()
            
            # Update rate limits based on exchange info
            if exchange_info.rate_limits:
                # Find the most restrictive limits
                rate_limits = self._parse_rate_limits(exchange_info.rate_limits)
                self.rate_limiter.update_rate_limits(rate_limits)
            
            self.exchange_info = exchange_info
            self.exchange_info_updated = time.time()
            
        except Exception as e:
            self.logger.error(f"Failed to load exchange info: {e}")
    
    def _parse_rate_limits(self, rate_limits: List[Dict[str, Any]]) -> RateLimit:
        """Parse rate limits from exchange info."""
        # Default conservative limits
        limits = RateLimit(
            requests_per_second=10,
            requests_per_minute=1200,
            requests_per_day=200000,
            weight_per_second=1200,
            weight_per_minute=6000,
            weight_per_day=1000000,
        )
        
        for limit in rate_limits:
            limit_type = limit.get('rateLimitType')
            interval = limit.get('interval')
            limit_value = limit.get('limit', 0)
            
            if limit_type == 'REQUEST_WEIGHT':
                if interval == 'SECOND':
                    limits.weight_per_second = limit_value
                elif interval == 'MINUTE':
                    limits.weight_per_minute = limit_value
                elif interval == 'DAY':
                    limits.weight_per_day = limit_value
            elif limit_type == 'ORDERS':
                if interval == 'SECOND':
                    limits.requests_per_second = limit_value
                elif interval == 'MINUTE':
                    limits.requests_per_minute = limit_value
                elif interval == 'DAY':
                    limits.requests_per_day = limit_value
        
        return limits
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for authenticated requests."""
        query_string = urlencode(params)
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        weight: int = 1
    ) -> Dict[str, Any]:
        """
        Make a request to the Binance API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            signed: Whether to sign the request
            weight: Request weight for rate limiting
            
        Returns:
            API response as dictionary
        """
        if not self.session:
            raise RuntimeError("Client not initialized")
        
        # Wait for rate limit
        await self.rate_limiter.wait_for_request(weight)
        
        # Prepare parameters
        if params is None:
            params = {}
        
        # Add timestamp for signed requests
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
        
        # Make request
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.request(
                method=method,
                url=url,
                params=params if method == 'GET' else None,
                data=params if method != 'GET' else None
            ) as response:
                
                # Handle rate limiting
                if response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 1))
                    self.logger.warning(f"Rate limited, waiting {retry_after} seconds")
                    await asyncio.sleep(retry_after)
                    return await self._make_request(method, endpoint, params, signed, weight)
                
                # Handle other errors
                if response.status >= 400:
                    error_text = await response.text()
                    self.logger.error(f"API error {response.status}: {error_text}")
                    raise Exception(f"API error {response.status}: {error_text}")
                
                return await response.json()
                
        except asyncio.TimeoutError:
            self.logger.error("Request timeout")
            raise
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            raise
    
    async def get_exchange_info(self) -> ExchangeInfo:
        """Get exchange information."""
        data = await self._make_request('GET', '/api/v3/exchangeInfo', weight=10)
        
        return ExchangeInfo(
            timezone=data.get('timezone', 'UTC'),
            server_time=time.time(),
            rate_limits=data.get('rateLimits', []),
            symbols=data.get('symbols', []),
            exchange_filters=data.get('exchangeFilters', [])
        )
    
    async def get_account_info(self) -> AccountInfo:
        """Get account information."""
        data = await self._make_request('GET', '/api/v3/account', signed=True, weight=10)
        
        balances = {}
        for balance in data.get('balances', []):
            asset = balance['asset']
            free = float(balance['free'])
            locked = float(balance['locked'])
            if free > 0 or locked > 0:
                balances[asset] = free + locked
        
        return AccountInfo(
            account_type=data.get('accountType', 'SPOT'),
            can_trade=data.get('canTrade', False),
            can_deposit=data.get('canDeposit', False),
            can_withdraw=data.get('canWithdraw', False),
            update_time=time.time(),
            balances=balances,
            permissions=data.get('permissions', [])
        )
    
    async def get_server_time(self) -> int:
        """Get server time."""
        data = await self._make_request('GET', '/api/v3/time', weight=1)
        return data['serverTime']
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        stop_price: Optional[float] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """
        Place an order.
        
        Args:
            symbol: Trading symbol
            side: Order side
            order_type: Order type
            quantity: Order quantity
            price: Order price (for limit orders)
            time_in_force: Time in force
            stop_price: Stop price (for stop orders)
            client_order_id: Client order ID
            
        Returns:
            Created order
        """
        params = {
            'symbol': symbol,
            'side': side.value,
            'type': order_type.value,
            'quantity': str(quantity),
            'timeInForce': time_in_force.value,
        }
        
        if price is not None:
            params['price'] = str(price)
        
        if stop_price is not None:
            params['stopPrice'] = str(stop_price)
        
        if client_order_id:
            params['newClientOrderId'] = client_order_id
        
        data = await self._make_request('POST', '/api/v3/order', params, signed=True, weight=1)
        
        return Order(
            symbol=data['symbol'],
            order_id=int(data['orderId']),
            client_order_id=data.get('clientOrderId'),
            side=OrderSide(data['side']),
            type=OrderType(data['type']),
            quantity=float(data['origQty']),
            price=float(data.get('price', 0)) if data.get('price') else None,
            stop_price=float(data.get('stopPrice', 0)) if data.get('stopPrice') else None,
            time_in_force=TimeInForce(data.get('timeInForce', 'GTC')),
            status=OrderStatus(data['status']),
            executed_qty=float(data.get('executedQty', 0)),
            cummulative_quote_qty=float(data.get('cummulativeQuoteQty', 0)),
            avg_price=float(data.get('avgPrice', 0)) if data.get('avgPrice') else None,
        )
    
    async def cancel_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """
        Cancel an order.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            client_order_id: Client order ID
            
        Returns:
            Canceled order
        """
        params = {'symbol': symbol}
        
        if order_id:
            params['orderId'] = order_id
        elif client_order_id:
            params['origClientOrderId'] = client_order_id
        else:
            raise ValueError("Either order_id or client_order_id must be provided")
        
        data = await self._make_request('DELETE', '/api/v3/order', params, signed=True, weight=1)
        
        return Order(
            symbol=data['symbol'],
            order_id=int(data['orderId']),
            client_order_id=data.get('clientOrderId'),
            side=OrderSide(data['side']),
            type=OrderType(data['type']),
            quantity=float(data['origQty']),
            price=float(data.get('price', 0)) if data.get('price') else None,
            time_in_force=TimeInForce(data.get('timeInForce', 'GTC')),
            status=OrderStatus(data['status']),
            executed_qty=float(data.get('executedQty', 0)),
            cummulative_quote_qty=float(data.get('cummulativeQuoteQty', 0)),
            avg_price=float(data.get('avgPrice', 0)) if data.get('avgPrice') else None,
        )
    
    async def get_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """
        Get order information.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            client_order_id: Client order ID
            
        Returns:
            Order information
        """
        params = {'symbol': symbol}
        
        if order_id:
            params['orderId'] = order_id
        elif client_order_id:
            params['origClientOrderId'] = client_order_id
        else:
            raise ValueError("Either order_id or client_order_id must be provided")
        
        data = await self._make_request('GET', '/api/v3/order', params, signed=True, weight=2)
        
        return Order(
            symbol=data['symbol'],
            order_id=int(data['orderId']),
            client_order_id=data.get('clientOrderId'),
            side=OrderSide(data['side']),
            type=OrderType(data['type']),
            quantity=float(data['origQty']),
            price=float(data.get('price', 0)) if data.get('price') else None,
            stop_price=float(data.get('stopPrice', 0)) if data.get('stopPrice') else None,
            time_in_force=TimeInForce(data.get('timeInForce', 'GTC')),
            status=OrderStatus(data['status']),
            executed_qty=float(data.get('executedQty', 0)),
            cummulative_quote_qty=float(data.get('cummulativeQuoteQty', 0)),
            avg_price=float(data.get('avgPrice', 0)) if data.get('avgPrice') else None,
        )
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Get open orders.
        
        Args:
            symbol: Trading symbol (optional)
            
        Returns:
            List of open orders
        """
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        data = await self._make_request('GET', '/api/v3/openOrders', params, signed=True, weight=3)
        
        orders = []
        for order_data in data:
            orders.append(Order(
                symbol=order_data['symbol'],
                order_id=int(order_data['orderId']),
                client_order_id=order_data.get('clientOrderId'),
                side=OrderSide(order_data['side']),
                type=OrderType(order_data['type']),
                quantity=float(order_data['origQty']),
                price=float(order_data.get('price', 0)) if order_data.get('price') else None,
                stop_price=float(order_data.get('stopPrice', 0)) if order_data.get('stopPrice') else None,
                time_in_force=TimeInForce(order_data.get('timeInForce', 'GTC')),
                status=OrderStatus(order_data['status']),
                executed_qty=float(order_data.get('executedQty', 0)),
                cummulative_quote_qty=float(order_data.get('cummulativeQuoteQty', 0)),
                avg_price=float(order_data.get('avgPrice', 0)) if order_data.get('avgPrice') else None,
            ))
        
        return orders
    
    async def get_24hr_ticker(self, symbol: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Get 24hr ticker price change statistics.
        
        Args:
            symbol: Trading symbol (optional)
            
        Returns:
            Ticker data
        """
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        return await self._make_request('GET', '/api/v3/ticker/24hr', params, weight=1)
    
    async def get_orderbook(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """
        Get order book.
        
        Args:
            symbol: Trading symbol
            limit: Number of levels (5, 10, 20, 50, 100, 500, 1000, 5000)
            
        Returns:
            Order book data
        """
        params = {
            'symbol': symbol,
            'limit': limit
        }
        
        return await self._make_request('GET', '/api/v3/depth', params, weight=1)
    
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500
    ) -> List[List[Any]]:
        """
        Get kline/candlestick data.
        
        Args:
            symbol: Trading symbol
            interval: Kline interval
            start_time: Start time in milliseconds
            end_time: End time in milliseconds
            limit: Number of klines
            
        Returns:
            Kline data
        """
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        return await self._make_request('GET', '/api/v3/klines', params, weight=1)
