"""
Binance WebSocket client for real-time market data.
Handles connection management, reconnection, and data streaming.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Callable, Any
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from ..types import OrderBook, Kline, MarketData, WebSocketMessage


class BinanceWebSocketClient:
    """
    Binance WebSocket client for real-time market data.
    
    Handles:
    - WebSocket connection management
    - Automatic reconnection
    - Data stream subscription
    - Message parsing and routing
    """
    
    def __init__(
        self,
        base_url: str = "wss://stream.binance.com:9443/ws",
        testnet: bool = False
    ):
        """
        Initialize WebSocket client.
        
        Args:
            base_url: WebSocket base URL
            testnet: Whether to use testnet
        """
        self.base_url = base_url
        self.testnet = testnet
        self.logger = logging.getLogger(__name__)
        
        # Connection state
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.is_connected = False
        self.is_running = False
        self.reconnect_interval = 5
        self.max_reconnect_attempts = 10
        self.reconnect_attempts = 0
        
        # Stream management
        self.subscribed_streams: List[str] = []
        self.stream_handlers: Dict[str, Callable] = {}
        
        # Message handlers
        self.on_market_data: Optional[Callable] = None
        self.on_orderbook_update: Optional[Callable] = None
        self.on_kline_update: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # Statistics
        self.messages_received = 0
        self.messages_processed = 0
        self.connection_errors = 0
        self.last_message_time = 0
    
    async def connect(self) -> None:
        """Establish WebSocket connection."""
        try:
            self.logger.info(f"Connecting to WebSocket: {self.base_url}")
            
            self.websocket = await websockets.connect(
                self.base_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.is_connected = True
            self.reconnect_attempts = 0
            self.logger.info("WebSocket connected successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to WebSocket: {e}")
            self.connection_errors += 1
            raise
    
    async def disconnect(self) -> None:
        """Disconnect WebSocket."""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        self.is_connected = False
        self.logger.info("WebSocket disconnected")
    
    async def subscribe_to_streams(self, streams: List[str]) -> None:
        """
        Subscribe to multiple streams.
        
        Args:
            streams: List of stream names to subscribe to
        """
        if not self.is_connected or not self.websocket:
            raise RuntimeError("WebSocket not connected")
        
        # Use combined stream if multiple streams
        if len(streams) > 1:
            stream_name = "/".join(streams)
            subscribe_message = {
                "method": "SUBSCRIBE",
                "params": streams,
                "id": int(time.time() * 1000)
            }
        else:
            stream_name = streams[0]
            subscribe_message = {
                "method": "SUBSCRIBE",
                "params": [stream_name],
                "id": int(time.time() * 1000)
            }
        
        await self.websocket.send(json.dumps(subscribe_message))
        self.subscribed_streams.extend(streams)
        
        self.logger.info(f"Subscribed to streams: {streams}")
    
    async def unsubscribe_from_streams(self, streams: List[str]) -> None:
        """
        Unsubscribe from streams.
        
        Args:
            streams: List of stream names to unsubscribe from
        """
        if not self.is_connected or not self.websocket:
            raise RuntimeError("WebSocket not connected")
        
        unsubscribe_message = {
            "method": "UNSUBSCRIBE",
            "params": streams,
            "id": int(time.time() * 1000)
        }
        
        await self.websocket.send(json.dumps(unsubscribe_message))
        
        for stream in streams:
            if stream in self.subscribed_streams:
                self.subscribed_streams.remove(stream)
        
        self.logger.info(f"Unsubscribed from streams: {streams}")
    
    async def start(self) -> None:
        """Start the WebSocket client."""
        self.is_running = True
        
        while self.is_running:
            try:
                await self.connect()
                await self._listen()
                
            except ConnectionClosed:
                self.logger.warning("WebSocket connection closed")
                self.is_connected = False
                
            except WebSocketException as e:
                self.logger.error(f"WebSocket error: {e}")
                self.connection_errors += 1
                
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                self.connection_errors += 1
            
            # Attempt reconnection
            if self.is_running and self.reconnect_attempts < self.max_reconnect_attempts:
                self.reconnect_attempts += 1
                self.logger.info(f"Attempting reconnection {self.reconnect_attempts}/{self.max_reconnect_attempts}")
                await asyncio.sleep(self.reconnect_interval)
            elif self.reconnect_attempts >= self.max_reconnect_attempts:
                self.logger.error("Max reconnection attempts reached, stopping")
                break
    
    async def stop(self) -> None:
        """Stop the WebSocket client."""
        self.is_running = False
        await self.disconnect()
    
    async def _listen(self) -> None:
        """Listen for WebSocket messages."""
        if not self.websocket:
            return
        
        async for message in self.websocket:
            try:
                await self._handle_message(message)
            except Exception as e:
                self.logger.error(f"Error handling message: {e}")
                if self.on_error:
                    await self.on_error(e)
    
    async def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            self.messages_received += 1
            self.last_message_time = time.time()
            
            # Handle subscription confirmations
            if 'result' in data and 'id' in data:
                self.logger.info(f"Subscription confirmed: {data}")
                return
            
            # Handle error messages
            if 'error' in data:
                self.logger.error(f"WebSocket error: {data}")
                if self.on_error:
                    await self.on_error(data['error'])
                return
            
            # Handle stream data
            if 'stream' in data and 'data' in data:
                await self._process_stream_data(data['stream'], data['data'])
            
            self.messages_processed += 1
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def _process_stream_data(self, stream: str, data: Dict[str, Any]) -> None:
        """Process stream data based on stream type."""
        try:
            if stream.endswith('@ticker'):
                await self._handle_ticker_data(stream, data)
            elif stream.endswith('@depth'):
                await self._handle_depth_data(stream, data)
            elif stream.endswith('@kline_'):
                await self._handle_kline_data(stream, data)
            elif stream.endswith('@aggTrade'):
                await self._handle_agg_trade_data(stream, data)
            else:
                self.logger.debug(f"Unknown stream type: {stream}")
                
        except Exception as e:
            self.logger.error(f"Error processing stream data for {stream}: {e}")
    
    async def _handle_ticker_data(self, stream: str, data: Dict[str, Any]) -> None:
        """Handle ticker data."""
        if not self.on_market_data:
            return
        
        symbol = data.get('s')
        if not symbol:
            return
        
        market_data = MarketData(
            symbol=symbol,
            timestamp=time.time(),
            price=float(data.get('c', 0)),  # Close price
            volume=float(data.get('v', 0)),  # Volume
            side='BUY' if float(data.get('P', 0)) >= 0 else 'SELL'  # Price change direction
        )
        
        await self.on_market_data(market_data)
    
    async def _handle_depth_data(self, stream: str, data: Dict[str, Any]) -> None:
        """Handle order book depth data."""
        if not self.on_orderbook_update:
            return
        
        symbol = data.get('s')
        if not symbol:
            return
        
        # Parse bids and asks
        bids = [
            {'price': float(price), 'quantity': float(quantity)}
            for price, quantity in data.get('b', [])
        ]
        asks = [
            {'price': float(price), 'quantity': float(quantity)}
            for price, quantity in data.get('a', [])
        ]
        
        orderbook = OrderBook(
            symbol=symbol,
            timestamp=time.time(),
            bids=bids,
            asks=asks,
            last_update_id=data.get('u', 0)
        )
        
        await self.on_orderbook_update(orderbook)
    
    async def _handle_kline_data(self, stream: str, data: Dict[str, Any]) -> None:
        """Handle kline/candlestick data."""
        if not self.on_kline_update:
            return
        
        kline_data = data.get('k')
        if not kline_data:
            return
        
        symbol = kline_data.get('s')
        if not symbol:
            return
        
        kline = Kline(
            symbol=symbol,
            open_time=time.time(),
            close_time=time.time(),
            open_price=float(kline_data.get('o', 0)),
            high_price=float(kline_data.get('h', 0)),
            low_price=float(kline_data.get('l', 0)),
            close_price=float(kline_data.get('c', 0)),
            volume=float(kline_data.get('v', 0)),
            quote_volume=float(kline_data.get('q', 0)),
            trades_count=int(kline_data.get('n', 0)),
            taker_buy_volume=float(kline_data.get('V', 0)),
            taker_buy_quote_volume=float(kline_data.get('Q', 0)),
            is_closed=kline_data.get('x', False)
        )
        
        await self.on_kline_update(kline)
    
    async def _handle_agg_trade_data(self, stream: str, data: Dict[str, Any]) -> None:
        """Handle aggregated trade data."""
        if not self.on_market_data:
            return
        
        symbol = data.get('s')
        if not symbol:
            return
        
        market_data = MarketData(
            symbol=symbol,
            timestamp=time.time(),
            price=float(data.get('p', 0)),
            volume=float(data.get('q', 0)),
            side='BUY' if data.get('m', False) else 'SELL'  # m=true means buyer is maker
        )
        
        await self.on_market_data(market_data)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket client statistics."""
        return {
            'is_connected': self.is_connected,
            'is_running': self.is_running,
            'subscribed_streams': self.subscribed_streams,
            'messages_received': self.messages_received,
            'messages_processed': self.messages_processed,
            'connection_errors': self.connection_errors,
            'reconnect_attempts': self.reconnect_attempts,
            'last_message_time': self.last_message_time,
        }
