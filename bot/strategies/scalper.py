"""
Scalper strategy implementation.
Uses orderbook imbalance and micro-mean-reversion for high-frequency trading.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from decimal import Decimal
from collections import deque

from .base import StrategyBase
from ..types import TradingSignal, MarketData, OrderBook, OrderSide, OrderType, TimeInForce


class ScalperStrategy(StrategyBase):
    """
    Scalper strategy using orderbook imbalance and micro-mean-reversion.
    
    Strategy Logic:
    1. Calculate orderbook imbalance (OBI) = (bid_volume - ask_volume) / (bid_volume + ask_volume)
    2. Use short and long EMAs for trend detection
    3. Generate signals when OBI > threshold and EMA_short > EMA_long
    4. Position sizing based on risk fraction and stop distance
    """
    
    def __init__(self, name: str, config: Dict[str, Any], symbols: List[str]):
        """Initialize scalper strategy."""
        super().__init__(name, config, symbols)
        
        # Strategy parameters
        self.ema_short = config.get('ema_short', 5)
        self.ema_long = config.get('ema_long', 20)
        self.obi_threshold = config.get('obi_threshold', 0.25)
        self.risk_fraction = config.get('risk_fraction', 0.01)
        self.stop_distance = config.get('stop_distance', 0.005)
        self.slip_offset = config.get('slip_offset', 0.0001)
        
        # Data storage
        self.price_history: Dict[str, deque] = {}
        self.obi_history: Dict[str, deque] = {}
        self.ema_short_values: Dict[str, Decimal] = {}
        self.ema_long_values: Dict[str, Decimal] = {}
        
        # Initialize data storage
        for symbol in symbols:
            self.price_history[symbol] = deque(maxlen=1000)
            self.obi_history[symbol] = deque(maxlen=100)
            self.ema_short_values[symbol] = Decimal('0')
            self.ema_long_values[symbol] = Decimal('0')
    
    async def _process_market_data(self, market_data: MarketData) -> None:
        """Process market data for scalper strategy."""
        try:
            symbol = market_data.symbol
            price = market_data.price
            
            # Store price history
            self.price_history[symbol].append(price)
            
            # Calculate EMAs
            if len(self.price_history[symbol]) >= self.ema_long:
                prices = list(self.price_history[symbol])
                self.ema_short_values[symbol] = self.calculate_ema(prices, self.ema_short)
                self.ema_long_values[symbol] = self.calculate_ema(prices, self.ema_long)
                
                # Check for trading signals
                await self._check_scalper_signals(symbol, price)
            
        except Exception as e:
            self.logger.error(f"Error processing market data: {e}")
    
    async def _process_orderbook(self, orderbook: OrderBook) -> None:
        """Process orderbook for scalper strategy."""
        try:
            symbol = orderbook.symbol
            
            # Calculate orderbook imbalance
            obi = self._calculate_orderbook_imbalance(orderbook)
            
            # Store OBI history
            self.obi_history[symbol].append(obi)
            
            # Check for trading signals
            if len(self.price_history[symbol]) >= self.ema_long:
                current_price = self.price_history[symbol][-1]
                await self._check_scalper_signals(symbol, current_price)
            
        except Exception as e:
            self.logger.error(f"Error processing orderbook: {e}")
    
    def _calculate_orderbook_imbalance(self, orderbook: OrderBook) -> Decimal:
        """
        Calculate orderbook imbalance.
        
        OBI = (bid_volume - ask_volume) / (bid_volume + ask_volume)
        
        Args:
            orderbook: Orderbook data
            
        Returns:
            Orderbook imbalance (-1 to 1)
        """
        try:
            # Sum top 5 levels for each side
            bid_volume = sum(level['quantity'] for level in orderbook.bids[:5])
            ask_volume = sum(level['quantity'] for level in orderbook.asks[:5])
            
            total_volume = bid_volume + ask_volume
            if total_volume == 0:
                return Decimal('0')
            
            obi = (bid_volume - ask_volume) / total_volume
            return obi
            
        except Exception as e:
            self.logger.error(f"Error calculating OBI: {e}")
            return Decimal('0')
    
    async def _check_scalper_signals(self, symbol: str, current_price: Decimal) -> None:
        """Check for scalper trading signals."""
        try:
            # Get current values
            ema_short = self.ema_short_values.get(symbol, Decimal('0'))
            ema_long = self.ema_long_values.get(symbol, Decimal('0'))
            obi = self.obi_history[symbol][-1] if self.obi_history[symbol] else Decimal('0')
            
            # Check if we have enough data
            if ema_short == 0 or ema_long == 0:
                return
            
            # Check for buy signal
            if (obi > self.obi_threshold and 
                ema_short > ema_long and 
                self.get_position(symbol) <= 0):
                
                await self._generate_buy_signal(symbol, current_price)
            
            # Check for sell signal
            elif (obi < -self.obi_threshold and 
                  ema_short < ema_long and 
                  self.get_position(symbol) >= 0):
                
                await self._generate_sell_signal(symbol, current_price)
            
        except Exception as e:
            self.logger.error(f"Error checking scalper signals: {e}")
    
    async def _generate_buy_signal(self, symbol: str, current_price: Decimal) -> None:
        """Generate buy signal for scalper strategy."""
        try:
            # Calculate position size
            position_size = self._calculate_position_size(symbol, current_price)
            
            if position_size <= 0:
                return
            
            # Calculate entry price with slippage offset
            entry_price = current_price * (1 - self.slip_offset)
            
            # Generate signal
            await self.generate_signal(
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=position_size,
                price=entry_price,
                order_type=OrderType.LIMIT,
                time_in_force=TimeInForce.IOC,
                confidence=0.8,
                metadata={
                    'strategy': 'scalper',
                    'signal_type': 'buy',
                    'obi': float(self.obi_history[symbol][-1]),
                    'ema_short': float(self.ema_short_values[symbol]),
                    'ema_long': float(self.ema_long_values[symbol]),
                    'entry_price': float(entry_price),
                    'stop_price': float(entry_price * (1 - self.stop_distance)),
                    'take_profit': float(entry_price * (1 + self.stop_distance * 2))
                }
            )
            
            self.logger.info(f"Generated buy signal for {symbol}: {position_size} @ {entry_price}")
            
        except Exception as e:
            self.logger.error(f"Error generating buy signal: {e}")
    
    async def _generate_sell_signal(self, symbol: str, current_price: Decimal) -> None:
        """Generate sell signal for scalper strategy."""
        try:
            # Calculate position size
            position_size = self._calculate_position_size(symbol, current_price)
            
            if position_size <= 0:
                return
            
            # Calculate entry price with slippage offset
            entry_price = current_price * (1 + self.slip_offset)
            
            # Generate signal
            await self.generate_signal(
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=position_size,
                price=entry_price,
                order_type=OrderType.LIMIT,
                time_in_force=TimeInForce.IOC,
                confidence=0.8,
                metadata={
                    'strategy': 'scalper',
                    'signal_type': 'sell',
                    'obi': float(self.obi_history[symbol][-1]),
                    'ema_short': float(self.ema_short_values[symbol]),
                    'ema_long': float(self.ema_long_values[symbol]),
                    'entry_price': float(entry_price),
                    'stop_price': float(entry_price * (1 + self.stop_distance)),
                    'take_profit': float(entry_price * (1 - self.stop_distance * 2))
                }
            )
            
            self.logger.info(f"Generated sell signal for {symbol}: {position_size} @ {entry_price}")
            
        except Exception as e:
            self.logger.error(f"Error generating sell signal: {e}")
    
    def _calculate_position_size(self, symbol: str, current_price: Decimal) -> Decimal:
        """
        Calculate position size based on risk management.
        
        size = equity * risk_fraction / (stop_distance * price)
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            
        Returns:
            Position size
        """
        try:
            # This is a simplified calculation
            # In practice, you'd get equity from account info
            equity = Decimal('10000')  # Mock equity
            
            # Calculate position size
            risk_amount = equity * self.risk_fraction
            stop_amount = current_price * self.stop_distance
            
            if stop_amount == 0:
                return Decimal('0')
            
            position_size = risk_amount / stop_amount
            
            # Apply position limits
            max_position = equity * Decimal('0.1') / current_price  # Max 10% of equity
            position_size = min(position_size, max_position)
            
            # Round to appropriate precision
            position_size = position_size.quantize(Decimal('0.001'))
            
            return position_size
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return Decimal('0')
    
    async def _process_fill(self, fill) -> None:
        """Process trade fills for scalper strategy."""
        try:
            symbol = fill.symbol
            side = fill.side
            quantity = fill.quantity
            price = fill.price
            
            # Update position
            if side == OrderSide.BUY:
                self.positions[symbol] += quantity
            else:
                self.positions[symbol] -= quantity
            
            # Update entry price
            if self.positions[symbol] != 0:
                self.entry_prices[symbol] = price
            
            # Log fill
            self.logger.info(f"Fill processed: {side} {quantity} {symbol} @ {price}")
            
            # Update performance metrics
            self.trades_executed += 1
            
        except Exception as e:
            self.logger.error(f"Error processing fill: {e}")
    
    async def on_timer(self) -> None:
        """Handle timer events for scalper strategy."""
        try:
            # Check for position management
            for symbol in self.symbols:
                position = self.get_position(symbol)
                if position != 0:
                    await self._manage_position(symbol, position)
            
        except Exception as e:
            self.logger.error(f"Error in timer: {e}")
    
    async def _manage_position(self, symbol: str, position: Decimal) -> None:
        """Manage existing positions."""
        try:
            current_price = self.get_market_price(symbol)
            if not current_price:
                return
            
            entry_price = self.get_entry_price(symbol)
            if entry_price == 0:
                return
            
            # Calculate P&L
            if position > 0:  # Long position
                pnl_pct = (current_price - entry_price) / entry_price
            else:  # Short position
                pnl_pct = (entry_price - current_price) / entry_price
            
            # Check stop loss
            if pnl_pct <= -self.stop_distance:
                await self._close_position(symbol, position, current_price, "stop_loss")
            
            # Check take profit
            elif pnl_pct >= self.stop_distance * 2:
                await self._close_position(symbol, position, current_price, "take_profit")
            
        except Exception as e:
            self.logger.error(f"Error managing position: {e}")
    
    async def _close_position(self, symbol: str, position: Decimal, current_price: Decimal, reason: str) -> None:
        """Close a position."""
        try:
            if position > 0:
                side = OrderSide.SELL
            else:
                side = OrderSide.BUY
                position = -position
            
            # Generate close signal
            await self.generate_signal(
                symbol=symbol,
                side=side,
                quantity=position,
                price=current_price,
                order_type=OrderType.MARKET,
                time_in_force=TimeInForce.IOC,
                confidence=1.0,
                metadata={
                    'strategy': 'scalper',
                    'signal_type': 'close',
                    'reason': reason,
                    'position': float(position),
                    'entry_price': float(self.get_entry_price(symbol)),
                    'exit_price': float(current_price)
                }
            )
            
            self.logger.info(f"Closing position: {side} {position} {symbol} @ {current_price} ({reason})")
            
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scalper strategy statistics."""
        stats = super().get_stats()
        
        # Add scalper-specific stats
        stats.update({
            'ema_short': self.ema_short,
            'ema_long': self.ema_long,
            'obi_threshold': self.obi_threshold,
            'risk_fraction': self.risk_fraction,
            'stop_distance': self.stop_distance,
            'current_obi': {
                symbol: float(self.obi_history[symbol][-1]) if self.obi_history[symbol] else 0.0
                for symbol in self.symbols
            },
            'current_ema_short': {
                symbol: float(self.ema_short_values[symbol])
                for symbol in self.symbols
            },
            'current_ema_long': {
                symbol: float(self.ema_long_values[symbol])
                for symbol in self.symbols
            }
        })
        
        return stats
