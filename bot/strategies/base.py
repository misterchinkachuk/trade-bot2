"""
Base strategy class and common utilities.
All trading strategies inherit from this base class.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from decimal import Decimal
from collections import deque

from ..types import TradingSignal, MarketData, OrderBook, Kline, OrderSide, OrderType, TimeInForce


class StrategyBase(ABC):
    """
    Base class for all trading strategies.
    
    Provides common functionality and interface for:
    - Market data processing
    - Signal generation
    - Position tracking
    - Performance monitoring
    """
    
    def __init__(self, name: str, config: Dict[str, Any], symbols: List[str]):
        """
        Initialize strategy.
        
        Args:
            name: Strategy name
            config: Strategy configuration
            symbols: List of symbols to trade
        """
        self.name = name
        self.config = config
        self.symbols = symbols
        self.logger = logging.getLogger(f"{__name__}.{name}")
        
        # State management
        self.is_enabled = False
        self.is_initialized = False
        
        # Market data storage
        self.market_data: Dict[str, MarketData] = {}
        self.orderbooks: Dict[str, OrderBook] = {}
        self.klines: Dict[str, Dict[str, List[Kline]]] = {}
        
        # Position tracking
        self.positions: Dict[str, Decimal] = {}
        self.entry_prices: Dict[str, Decimal] = {}
        
        # Performance tracking
        self.signals_generated = 0
        self.trades_executed = 0
        self.total_pnl = Decimal('0')
        self.win_rate = Decimal('0')
        self.sharpe_ratio = Decimal('0')
        
        # Event handlers
        self.on_signal: Optional[Callable] = None
        
        # Timer for periodic tasks
        self.timer_task: Optional[asyncio.Task] = None
        self.timer_interval = 1.0  # seconds
    
    async def initialize(self) -> None:
        """Initialize the strategy."""
        try:
            # Initialize kline storage
            for symbol in self.symbols:
                self.klines[symbol] = {
                    '1m': deque(maxlen=1000),
                    '5m': deque(maxlen=1000),
                    '15m': deque(maxlen=1000),
                    '1h': deque(maxlen=1000)
                }
            
            # Initialize positions
            for symbol in self.symbols:
                self.positions[symbol] = Decimal('0')
                self.entry_prices[symbol] = Decimal('0')
            
            self.is_initialized = True
            self.logger.info(f"Strategy {self.name} initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize strategy {self.name}: {e}")
            raise
    
    async def enable(self) -> None:
        """Enable the strategy."""
        if not self.is_initialized:
            await self.initialize()
        
        self.is_enabled = True
        self.logger.info(f"Strategy {self.name} enabled")
    
    async def disable(self) -> None:
        """Disable the strategy."""
        self.is_enabled = False
        
        # Cancel timer task
        if self.timer_task:
            self.timer_task.cancel()
            self.timer_task = None
        
        self.logger.info(f"Strategy {self.name} disabled")
    
    async def start_timer(self) -> None:
        """Start the strategy timer for periodic tasks."""
        if not self.is_enabled:
            return
        
        try:
            while self.is_enabled:
                await self.on_timer()
                await asyncio.sleep(self.timer_interval)
                
        except asyncio.CancelledError:
            self.logger.info(f"Timer cancelled for strategy {self.name}")
        except Exception as e:
            self.logger.error(f"Error in strategy timer: {e}")
    
    async def on_market_data(self, market_data: MarketData) -> None:
        """
        Handle incoming market data.
        
        Args:
            market_data: Market data update
        """
        if not self.is_enabled:
            return
        
        try:
            # Store market data
            self.market_data[market_data.symbol] = market_data
            
            # Process market data
            await self._process_market_data(market_data)
            
        except Exception as e:
            self.logger.error(f"Error processing market data: {e}")
    
    async def on_orderbook_update(self, orderbook: OrderBook) -> None:
        """
        Handle orderbook updates.
        
        Args:
            orderbook: Orderbook update
        """
        if not self.is_enabled:
            return
        
        try:
            # Store orderbook
            self.orderbooks[orderbook.symbol] = orderbook
            
            # Process orderbook
            await self._process_orderbook(orderbook)
            
        except Exception as e:
            self.logger.error(f"Error processing orderbook: {e}")
    
    async def on_kline_update(self, kline: Kline) -> None:
        """
        Handle kline updates.
        
        Args:
            kline: Kline update
        """
        if not self.is_enabled:
            return
        
        try:
            # Store kline
            symbol = kline.symbol
            interval = '1m'  # Default interval
            
            if symbol in self.klines and interval in self.klines[symbol]:
                self.klines[symbol][interval].append(kline)
            
            # Process kline
            await self._process_kline(kline)
            
        except Exception as e:
            self.logger.error(f"Error processing kline: {e}")
    
    async def on_fill(self, fill) -> None:
        """
        Handle trade fills.
        
        Args:
            fill: Trade fill
        """
        if not self.is_enabled:
            return
        
        try:
            # Update position
            symbol = fill.symbol
            if fill.side == OrderSide.BUY:
                self.positions[symbol] += fill.quantity
            else:
                self.positions[symbol] -= fill.quantity
            
            # Update entry price
            if self.positions[symbol] != 0:
                self.entry_prices[symbol] = fill.price
            
            # Process fill
            await self._process_fill(fill)
            
        except Exception as e:
            self.logger.error(f"Error processing fill: {e}")
    
    async def on_timer(self) -> None:
        """
        Handle timer events for periodic tasks.
        Override this method in subclasses.
        """
        pass
    
    async def _process_market_data(self, market_data: MarketData) -> None:
        """
        Process market data.
        Override this method in subclasses.
        
        Args:
            market_data: Market data to process
        """
        pass
    
    async def _process_orderbook(self, orderbook: OrderBook) -> None:
        """
        Process orderbook updates.
        Override this method in subclasses.
        
        Args:
            orderbook: Orderbook to process
        """
        pass
    
    async def _process_kline(self, kline: Kline) -> None:
        """
        Process kline updates.
        Override this method in subclasses.
        
        Args:
            kline: Kline to process
        """
        pass
    
    async def _process_fill(self, fill) -> None:
        """
        Process trade fills.
        Override this method in subclasses.
        
        Args:
            fill: Fill to process
        """
        pass
    
    async def generate_signal(
        self,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        order_type: OrderType = OrderType.LIMIT,
        time_in_force: TimeInForce = TimeInForce.GTC,
        stop_price: Optional[Decimal] = None,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Generate a trading signal.
        
        Args:
            symbol: Trading symbol
            side: Order side
            quantity: Order quantity
            price: Order price (for limit orders)
            order_type: Order type
            time_in_force: Time in force
            stop_price: Stop price (for stop orders)
            confidence: Signal confidence (0.0 to 1.0)
            metadata: Additional signal metadata
        """
        try:
            signal = TradingSignal(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type,
                time_in_force=time_in_force,
                stop_price=stop_price,
                strategy_name=self.name,
                confidence=confidence,
                metadata=metadata or {}
            )
            
            # Notify signal handler
            if self.on_signal:
                await self.on_signal(signal)
            
            self.signals_generated += 1
            self.logger.debug(f"Generated signal: {signal}")
            
        except Exception as e:
            self.logger.error(f"Error generating signal: {e}")
    
    def get_position(self, symbol: str) -> Decimal:
        """Get current position for a symbol."""
        return self.positions.get(symbol, Decimal('0'))
    
    def get_entry_price(self, symbol: str) -> Decimal:
        """Get entry price for a symbol."""
        return self.entry_prices.get(symbol, Decimal('0'))
    
    def get_market_price(self, symbol: str) -> Optional[Decimal]:
        """Get current market price for a symbol."""
        market_data = self.market_data.get(symbol)
        return market_data.price if market_data else None
    
    def get_orderbook(self, symbol: str) -> Optional[OrderBook]:
        """Get current orderbook for a symbol."""
        return self.orderbooks.get(symbol)
    
    def get_klines(self, symbol: str, interval: str = '1m', limit: int = 100) -> List[Kline]:
        """Get klines for a symbol."""
        if symbol in self.klines and interval in self.klines[symbol]:
            return list(self.klines[symbol][interval])[-limit:]
        return []
    
    def calculate_ema(self, prices: List[Decimal], period: int) -> Decimal:
        """
        Calculate Exponential Moving Average.
        
        Args:
            prices: List of prices
            period: EMA period
            
        Returns:
            EMA value
        """
        if len(prices) < period:
            return Decimal('0')
        
        alpha = Decimal('2') / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return ema
    
    def calculate_sma(self, prices: List[Decimal], period: int) -> Decimal:
        """
        Calculate Simple Moving Average.
        
        Args:
            prices: List of prices
            period: SMA period
            
        Returns:
            SMA value
        """
        if len(prices) < period:
            return Decimal('0')
        
        return sum(prices[-period:]) / period
    
    def calculate_rsi(self, prices: List[Decimal], period: int = 14) -> Decimal:
        """
        Calculate Relative Strength Index.
        
        Args:
            prices: List of prices
            period: RSI period
            
        Returns:
            RSI value (0-100)
        """
        if len(prices) < period + 1:
            return Decimal('50')
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(Decimal('0'))
            else:
                gains.append(Decimal('0'))
                losses.append(-change)
        
        if len(gains) < period:
            return Decimal('50')
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return Decimal('100')
        
        rs = avg_gain / avg_loss
        rsi = Decimal('100') - (Decimal('100') / (1 + rs))
        
        return rsi
    
    def calculate_bollinger_bands(self, prices: List[Decimal], period: int = 20, std_dev: int = 2) -> Dict[str, Decimal]:
        """
        Calculate Bollinger Bands.
        
        Args:
            prices: List of prices
            period: Period for calculation
            std_dev: Standard deviation multiplier
            
        Returns:
            Dictionary with 'upper', 'middle', 'lower' bands
        """
        if len(prices) < period:
            return {'upper': Decimal('0'), 'middle': Decimal('0'), 'lower': Decimal('0')}
        
        sma = self.calculate_sma(prices, period)
        
        # Calculate standard deviation
        variance = sum((price - sma) ** 2 for price in prices[-period:]) / period
        std = variance.sqrt()
        
        return {
            'upper': sma + (std * std_dev),
            'middle': sma,
            'lower': sma - (std * std_dev)
        }
    
    def calculate_atr(self, high_prices: List[Decimal], low_prices: List[Decimal], close_prices: List[Decimal], period: int = 14) -> Decimal:
        """
        Calculate Average True Range.
        
        Args:
            high_prices: List of high prices
            low_prices: List of low prices
            close_prices: List of close prices
            period: ATR period
            
        Returns:
            ATR value
        """
        if len(high_prices) < period + 1:
            return Decimal('0')
        
        true_ranges = []
        
        for i in range(1, len(high_prices)):
            high = high_prices[i]
            low = low_prices[i]
            prev_close = close_prices[i-1]
            
            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            
            true_range = max(tr1, tr2, tr3)
            true_ranges.append(true_range)
        
        if len(true_ranges) < period:
            return Decimal('0')
        
        return sum(true_ranges[-period:]) / period
    
    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        return {
            'name': self.name,
            'enabled': self.is_enabled,
            'initialized': self.is_initialized,
            'symbols': self.symbols,
            'positions': {symbol: float(pos) for symbol, pos in self.positions.items()},
            'signals_generated': self.signals_generated,
            'trades_executed': self.trades_executed,
            'total_pnl': float(self.total_pnl),
            'win_rate': float(self.win_rate),
            'sharpe_ratio': float(self.sharpe_ratio),
        }
