"""
Market data ingestion and processing module.
Handles WebSocket streams, data normalization, and storage.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from decimal import Decimal
import redis.asyncio as redis
import asyncpg

from .config import Config
from .types import MarketData, OrderBook, Kline, OrderBookLevel
from .connectors import BinanceWebSocketClient, BinanceRESTClient


class MarketDataIngester:
    """
    Market data ingestion and processing.
    
    Handles:
    - WebSocket stream management
    - Data normalization and aggregation
    - Real-time orderbook maintenance
    - Kline/candlestick aggregation
    - Data storage and caching
    """
    
    def __init__(self, config: Config):
        """Initialize market data ingester."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # WebSocket client
        self.ws_client: Optional[BinanceWebSocketClient] = None
        self.rest_client: Optional[BinanceRESTClient] = None
        
        # Data storage
        self.redis_client: Optional[redis.Redis] = None
        self.db_pool: Optional[asyncpg.Pool] = None
        
        # Orderbook management
        self.orderbooks: Dict[str, OrderBook] = {}
        self.orderbook_sequences: Dict[str, int] = {}
        
        # Kline aggregation
        self.kline_buffers: Dict[str, Dict[str, List[Kline]]] = defaultdict(lambda: defaultdict(list))
        self.kline_intervals = ['1s', '1m', '5m', '15m', '1h', '4h', '1d']
        
        # VWAP calculation
        self.vwap_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'volume_sum': Decimal('0'),
            'price_volume_sum': Decimal('0'),
            'last_update': 0
        })
        
        # Event handlers
        self.on_market_data: Optional[Callable] = None
        self.on_orderbook_update: Optional[Callable] = None
        self.on_kline_update: Optional[Callable] = None
        
        # Statistics
        self.data_points_processed = 0
        self.orderbook_updates = 0
        self.kline_updates = 0
        self.last_data_time = 0
    
    async def initialize(self) -> None:
        """Initialize the data ingester."""
        try:
            # Initialize Redis
            self.redis_client = redis.Redis(
                host=self.config.redis.host,
                port=self.config.redis.port,
                db=self.config.redis.database,
                password=self.config.redis.password,
                decode_responses=True
            )
            
            # Initialize database pool
            self.db_pool = await asyncpg.create_pool(
                host=self.config.database.host,
                port=self.config.database.port,
                database=self.config.database.database,
                user=self.config.database.username,
                password=self.config.database.password,
                min_size=5,
                max_size=20
            )
            
            # Initialize WebSocket client
            self.ws_client = BinanceWebSocketClient(
                base_url=self.config.binance.ws_base_url,
                testnet=self.config.binance.testnet
            )
            
            # Initialize REST client
            self.rest_client = BinanceRESTClient(
                api_key=self.config.binance.api_key or "",
                api_secret=self.config.binance.api_secret or "",
                base_url=self.config.binance.base_url,
                testnet=self.config.binance.testnet
            )
            
            # Setup WebSocket handlers
            self.ws_client.on_market_data = self._on_market_data
            self.ws_client.on_orderbook_update = self._on_orderbook_update
            self.ws_client.on_kline_update = self._on_kline_update
            self.ws_client.on_error = self._on_ws_error
            
            self.logger.info("Market data ingester initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize market data ingester: {e}")
            raise
    
    async def start(self) -> None:
        """Start data ingestion."""
        if not self.ws_client:
            raise RuntimeError("Data ingester not initialized")
        
        try:
            # Subscribe to market data streams
            await self._subscribe_to_streams()
            
            # Start WebSocket client
            await self.ws_client.start()
            
        except Exception as e:
            self.logger.error(f"Failed to start data ingestion: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop data ingestion."""
        if self.ws_client:
            await self.ws_client.stop()
        
        if self.redis_client:
            await self.redis_client.close()
        
        if self.db_pool:
            await self.db_pool.close()
    
    async def _subscribe_to_streams(self) -> None:
        """Subscribe to required market data streams."""
        streams = []
        
        for symbol in self.config.trading.symbols:
            symbol_lower = symbol.lower()
            
            # Add streams for each symbol
            streams.extend([
                f"{symbol_lower}@ticker",           # 24hr ticker
                f"{symbol_lower}@depth@100ms",      # Order book depth
                f"{symbol_lower}@kline_1m",         # 1-minute klines
                f"{symbol_lower}@aggTrade",         # Aggregated trades
            ])
        
        await self.ws_client.subscribe_to_streams(streams)
        self.logger.info(f"Subscribed to {len(streams)} streams")
    
    async def _on_market_data(self, market_data: MarketData) -> None:
        """Handle incoming market data."""
        try:
            # Update VWAP
            await self._update_vwap(market_data)
            
            # Store in Redis for real-time access
            await self._store_market_data(market_data)
            
            # Notify handlers
            if self.on_market_data:
                await self.on_market_data(market_data)
            
            self.data_points_processed += 1
            self.last_data_time = time.time()
            
        except Exception as e:
            self.logger.error(f"Error handling market data: {e}")
    
    async def _on_orderbook_update(self, orderbook: OrderBook) -> None:
        """Handle orderbook updates."""
        try:
            # Update local orderbook
            self.orderbooks[orderbook.symbol] = orderbook
            
            # Store in Redis
            await self._store_orderbook(orderbook)
            
            # Notify handlers
            if self.on_orderbook_update:
                await self.on_orderbook_update(orderbook)
            
            self.orderbook_updates += 1
            
        except Exception as e:
            self.logger.error(f"Error handling orderbook update: {e}")
    
    async def _on_kline_update(self, kline: Kline) -> None:
        """Handle kline updates."""
        try:
            # Update kline buffers
            await self._update_kline_buffers(kline)
            
            # Store in database
            await self._store_kline(kline)
            
            # Notify handlers
            if self.on_kline_update:
                await self.on_kline_update(kline)
            
            self.kline_updates += 1
            
        except Exception as e:
            self.logger.error(f"Error handling kline update: {e}")
    
    async def _on_ws_error(self, error: Any) -> None:
        """Handle WebSocket errors."""
        self.logger.error(f"WebSocket error: {error}")
    
    async def _update_vwap(self, market_data: MarketData) -> None:
        """Update VWAP calculation."""
        symbol = market_data.symbol
        price = market_data.price
        volume = market_data.volume
        
        vwap_data = self.vwap_data[symbol]
        
        # Update VWAP calculation
        vwap_data['price_volume_sum'] += price * volume
        vwap_data['volume_sum'] += volume
        vwap_data['last_update'] = time.time()
        
        # Calculate VWAP
        if vwap_data['volume_sum'] > 0:
            vwap = vwap_data['price_volume_sum'] / vwap_data['volume_sum']
            
            # Store VWAP in Redis
            await self.redis_client.hset(
                f"vwap:{symbol}",
                mapping={
                    'vwap': str(vwap),
                    'volume': str(vwap_data['volume_sum']),
                    'timestamp': str(time.time())
                }
            )
    
    async def _update_kline_buffers(self, kline: Kline) -> None:
        """Update kline buffers for different timeframes."""
        symbol = kline.symbol
        
        # Add to 1-minute buffer
        self.kline_buffers[symbol]['1m'].append(kline)
        
        # Keep only last 1000 klines
        if len(self.kline_buffers[symbol]['1m']) > 1000:
            self.kline_buffers[symbol]['1m'] = self.kline_buffers[symbol]['1m'][-1000:]
        
        # Generate higher timeframe klines
        await self._generate_higher_timeframe_klines(symbol, kline)
    
    async def _generate_higher_timeframe_klines(self, symbol: str, kline: Kline) -> None:
        """Generate higher timeframe klines from 1-minute data."""
        minute_klines = self.kline_buffers[symbol]['1m']
        
        if len(minute_klines) < 5:
            return
        
        # Generate 5-minute klines
        if len(minute_klines) >= 5 and len(minute_klines) % 5 == 0:
            await self._aggregate_klines(symbol, minute_klines[-5:], '5m')
        
        # Generate 15-minute klines
        if len(minute_klines) >= 15 and len(minute_klines) % 15 == 0:
            await self._aggregate_klines(symbol, minute_klines[-15:], '15m')
        
        # Generate 1-hour klines
        if len(minute_klines) >= 60 and len(minute_klines) % 60 == 0:
            await self._aggregate_klines(symbol, minute_klines[-60:], '1h')
    
    async def _aggregate_klines(self, symbol: str, klines: List[Kline], interval: str) -> None:
        """Aggregate klines into higher timeframe."""
        if not klines:
            return
        
        # Calculate aggregated kline
        open_price = klines[0].open_price
        close_price = klines[-1].close_price
        high_price = max(k.high_price for k in klines)
        low_price = min(k.low_price for k in klines)
        volume = sum(k.volume for k in klines)
        quote_volume = sum(k.quote_volume for k in klines)
        trades_count = sum(k.trades_count for k in klines)
        taker_buy_volume = sum(k.taker_buy_volume for k in klines)
        taker_buy_quote_volume = sum(k.taker_buy_quote_volume for k in klines)
        
        aggregated_kline = Kline(
            symbol=symbol,
            open_time=klines[0].open_time,
            close_time=klines[-1].close_time,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=volume,
            quote_volume=quote_volume,
            trades_count=trades_count,
            taker_buy_volume=taker_buy_volume,
            taker_buy_quote_volume=taker_buy_quote_volume,
            is_closed=True
        )
        
        # Store in buffer
        self.kline_buffers[symbol][interval].append(aggregated_kline)
        
        # Keep only last 1000 klines
        if len(self.kline_buffers[symbol][interval]) > 1000:
            self.kline_buffers[symbol][interval] = self.kline_buffers[symbol][interval][-1000:]
        
        # Store in database
        await self._store_kline(aggregated_kline, interval)
    
    async def _store_market_data(self, market_data: MarketData) -> None:
        """Store market data in Redis."""
        try:
            key = f"market_data:{market_data.symbol}"
            data = {
                'price': str(market_data.price),
                'volume': str(market_data.volume),
                'side': market_data.side.value,
                'timestamp': str(market_data.timestamp)
            }
            
            await self.redis_client.hset(key, mapping=data)
            await self.redis_client.expire(key, 3600)  # Expire after 1 hour
            
        except Exception as e:
            self.logger.error(f"Error storing market data: {e}")
    
    async def _store_orderbook(self, orderbook: OrderBook) -> None:
        """Store orderbook in Redis."""
        try:
            key = f"orderbook:{orderbook.symbol}"
            
            # Store bids and asks
            bids_data = {f"bid_{i}": f"{level['price']},{level['quantity']}" 
                        for i, level in enumerate(orderbook.bids[:20])}
            asks_data = {f"ask_{i}": f"{level['price']},{level['quantity']}" 
                        for i, level in enumerate(orderbook.asks[:20])}
            
            data = {
                'timestamp': str(orderbook.timestamp),
                'last_update_id': str(orderbook.last_update_id),
                **bids_data,
                **asks_data
            }
            
            await self.redis_client.hset(key, mapping=data)
            await self.redis_client.expire(key, 60)  # Expire after 1 minute
            
        except Exception as e:
            self.logger.error(f"Error storing orderbook: {e}")
    
    async def _store_kline(self, kline: Kline, interval: str = '1m') -> None:
        """Store kline in database."""
        try:
            if not self.db_pool:
                return
            
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO klines (symbol, interval, open_time, close_time, open_price, 
                                      high_price, low_price, close_price, volume, quote_volume,
                                      trades_count, taker_buy_volume, taker_buy_quote_volume, is_closed)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    ON CONFLICT (symbol, interval, open_time) 
                    DO UPDATE SET
                        close_time = EXCLUDED.close_time,
                        close_price = EXCLUDED.close_price,
                        high_price = EXCLUDED.high_price,
                        low_price = EXCLUDED.low_price,
                        volume = EXCLUDED.volume,
                        quote_volume = EXCLUDED.quote_volume,
                        trades_count = EXCLUDED.trades_count,
                        taker_buy_volume = EXCLUDED.taker_buy_volume,
                        taker_buy_quote_volume = EXCLUDED.taker_buy_quote_volume,
                        is_closed = EXCLUDED.is_closed
                """, 
                kline.symbol, interval, kline.open_time, kline.close_time,
                kline.open_price, kline.high_price, kline.low_price, kline.close_price,
                kline.volume, kline.quote_volume, kline.trades_count,
                kline.taker_buy_volume, kline.taker_buy_quote_volume, kline.is_closed
                )
                
        except Exception as e:
            self.logger.error(f"Error storing kline: {e}")
    
    async def get_latest_price(self, symbol: str) -> Optional[Decimal]:
        """Get latest price for a symbol."""
        try:
            if not self.redis_client:
                return None
            
            data = await self.redis_client.hget(f"market_data:{symbol}", "price")
            return Decimal(data) if data else None
            
        except Exception as e:
            self.logger.error(f"Error getting latest price: {e}")
            return None
    
    async def get_orderbook(self, symbol: str) -> Optional[OrderBook]:
        """Get current orderbook for a symbol."""
        return self.orderbooks.get(symbol)
    
    async def get_vwap(self, symbol: str) -> Optional[Decimal]:
        """Get current VWAP for a symbol."""
        try:
            if not self.redis_client:
                return None
            
            data = await self.redis_client.hget(f"vwap:{symbol}", "vwap")
            return Decimal(data) if data else None
            
        except Exception as e:
            self.logger.error(f"Error getting VWAP: {e}")
            return None
    
    async def get_klines(
        self, 
        symbol: str, 
        interval: str = '1m', 
        limit: int = 100
    ) -> List[Kline]:
        """Get historical klines for a symbol."""
        try:
            if not self.db_pool:
                return []
            
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM klines 
                    WHERE symbol = $1 AND interval = $2 
                    ORDER BY open_time DESC 
                    LIMIT $3
                """, symbol, interval, limit)
                
                klines = []
                for row in rows:
                    klines.append(Kline(
                        symbol=row['symbol'],
                        open_time=row['open_time'],
                        close_time=row['close_time'],
                        open_price=row['open_price'],
                        high_price=row['high_price'],
                        low_price=row['low_price'],
                        close_price=row['close_price'],
                        volume=row['volume'],
                        quote_volume=row['quote_volume'],
                        trades_count=row['trades_count'],
                        taker_buy_volume=row['taker_buy_volume'],
                        taker_buy_quote_volume=row['taker_buy_quote_volume'],
                        is_closed=row['is_closed']
                    ))
                
                return klines
                
        except Exception as e:
            self.logger.error(f"Error getting klines: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get data ingester statistics."""
        return {
            'data_points_processed': self.data_points_processed,
            'orderbook_updates': self.orderbook_updates,
            'kline_updates': self.kline_updates,
            'last_data_time': self.last_data_time,
            'active_orderbooks': len(self.orderbooks),
            'ws_client_stats': self.ws_client.get_stats() if self.ws_client else {},
        }
