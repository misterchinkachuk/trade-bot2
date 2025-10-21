"""
Market maker strategy implementation.
Uses continuous symmetric limit orders with inventory skewing.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal
from collections import deque

from .base import StrategyBase
from ..types import TradingSignal, MarketData, OrderBook, OrderSide, OrderType, TimeInForce


class MarketMakerStrategy(StrategyBase):
    """
    Market maker strategy using continuous symmetric limit orders.
    
    Strategy Logic:
    1. Place symmetric limit orders around mid-price
    2. Use inventory skewing to control delta
    3. Adjust spread based on volatility and fees
    4. Refresh orders periodically to maintain quotes
    """
    
    def __init__(self, name: str, config: Dict[str, Any], symbols: List[str]):
        """Initialize market maker strategy."""
        super().__init__(name, config, symbols)
        
        # Strategy parameters
        self.spread_pct = config.get('spread_pct', 0.001)  # 0.1% spread
        self.inventory_bias = config.get('inventory_bias', 0.1)  # Inventory bias coefficient
        self.refresh_interval = config.get('refresh_interval', 5)  # Order refresh interval (seconds)
        self.max_inventory = config.get('max_inventory', 1000)  # Maximum inventory
        self.order_size = config.get('order_size', 100)  # Order size
        self.volatility_window = config.get('volatility_window', 20)  # Volatility calculation window
        
        # Data storage
        self.price_history: Dict[str, deque] = {}
        self.volatility: Dict[str, Decimal] = {}
        self.last_refresh: Dict[str, float] = {}
        self.active_orders: Dict[str, List[str]] = {}  # Symbol -> List of order IDs
        
        # Initialize data storage
        for symbol in symbols:
            self.price_history[symbol] = deque(maxlen=1000)
            self.volatility[symbol] = Decimal('0')
            self.last_refresh[symbol] = 0
            self.active_orders[symbol] = []
    
    async def _process_market_data(self, market_data: MarketData) -> None:
        """Process market data for market maker strategy."""
        try:
            symbol = market_data.symbol
            price = market_data.price
            
            # Store price history
            self.price_history[symbol].append(price)
            
            # Calculate volatility
            if len(self.price_history[symbol]) >= self.volatility_window:
                self.volatility[symbol] = self._calculate_volatility(symbol)
            
            # Check if we need to refresh orders
            if time.time() - self.last_refresh[symbol] >= self.refresh_interval:
                await self._refresh_orders(symbol)
            
        except Exception as e:
            self.logger.error(f"Error processing market data: {e}")
    
    async def _process_orderbook(self, orderbook: OrderBook) -> None:
        """Process orderbook for market maker strategy."""
        try:
            symbol = orderbook.symbol
            
            # Check if we need to refresh orders
            if time.time() - self.last_refresh[symbol] >= self.refresh_interval:
                await self._refresh_orders(symbol)
            
        except Exception as e:
            self.logger.error(f"Error processing orderbook: {e}")
    
    def _calculate_volatility(self, symbol: str) -> Decimal:
        """
        Calculate price volatility.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Volatility value
        """
        try:
            prices = list(self.price_history[symbol])
            if len(prices) < self.volatility_window:
                return Decimal('0')
            
            # Calculate returns
            returns = []
            for i in range(1, len(prices)):
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)
            
            # Calculate standard deviation
            if len(returns) < 2:
                return Decimal('0')
            
            mean_return = sum(returns) / len(returns)
            variance = sum((ret - mean_return) ** 2 for ret in returns) / len(returns)
            volatility = variance.sqrt()
            
            return volatility
            
        except Exception as e:
            self.logger.error(f"Error calculating volatility: {e}")
            return Decimal('0')
    
    async def _refresh_orders(self, symbol: str) -> None:
        """Refresh market maker orders for a symbol."""
        try:
            # Cancel existing orders
            await self._cancel_existing_orders(symbol)
            
            # Get current market data
            orderbook = self.get_orderbook(symbol)
            if not orderbook:
                return
            
            # Calculate fair price and spread
            fair_price = self._calculate_fair_price(symbol, orderbook)
            spread = self._calculate_spread(symbol, fair_price)
            
            # Calculate quote prices
            quote_bid = fair_price - spread / 2
            quote_ask = fair_price + spread / 2
            
            # Place bid order
            if quote_bid > 0:
                await self._place_bid_order(symbol, quote_bid)
            
            # Place ask order
            if quote_ask > 0:
                await self._place_ask_order(symbol, quote_ask)
            
            # Update refresh time
            self.last_refresh[symbol] = time.time()
            
        except Exception as e:
            self.logger.error(f"Error refreshing orders: {e}")
    
    def _calculate_fair_price(self, symbol: str, orderbook: OrderBook) -> Decimal:
        """
        Calculate fair price with inventory skewing.
        
        fair_price = mid_price + λ * inventory
        
        Args:
            symbol: Trading symbol
            orderbook: Orderbook data
            
        Returns:
            Fair price
        """
        try:
            # Calculate mid-price
            if not orderbook.bids or not orderbook.asks:
                return Decimal('0')
            
            best_bid = orderbook.bids[0]['price']
            best_ask = orderbook.asks[0]['price']
            mid_price = (best_bid + best_ask) / 2
            
            # Apply inventory skewing
            inventory = self.get_position(symbol)
            skew = self.inventory_bias * inventory
            fair_price = mid_price + skew
            
            return fair_price
            
        except Exception as e:
            self.logger.error(f"Error calculating fair price: {e}")
            return Decimal('0')
    
    def _calculate_spread(self, symbol: str, fair_price: Decimal) -> Decimal:
        """
        Calculate spread based on volatility and fees.
        
        spread = f(volatility, fee, target_return)
        
        Args:
            symbol: Trading symbol
            fair_price: Fair price
            
        Returns:
            Spread amount
        """
        try:
            # Base spread
            base_spread = fair_price * self.spread_pct
            
            # Adjust for volatility
            volatility = self.volatility.get(symbol, Decimal('0'))
            volatility_adjustment = 1 + volatility * 2  # Increase spread with volatility
            
            # Adjust for inventory
            inventory = self.get_position(symbol)
            inventory_adjustment = 1 + abs(inventory) / self.max_inventory * 0.5
            
            # Calculate final spread
            spread = base_spread * volatility_adjustment * inventory_adjustment
            
            # Ensure minimum spread
            min_spread = fair_price * Decimal('0.0001')  # 0.01% minimum
            spread = max(spread, min_spread)
            
            return spread
            
        except Exception as e:
            self.logger.error(f"Error calculating spread: {e}")
            return fair_price * self.spread_pct
    
    async def _place_bid_order(self, symbol: str, price: Decimal) -> None:
        """Place bid order."""
        try:
            # Calculate order size based on inventory
            inventory = self.get_position(symbol)
            max_size = self.max_inventory - inventory
            
            if max_size <= 0:
                return
            
            order_size = min(self.order_size, max_size)
            
            # Generate signal
            await self.generate_signal(
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=order_size,
                price=price,
                order_type=OrderType.LIMIT,
                time_in_force=TimeInForce.GTC,
                confidence=0.9,
                metadata={
                    'strategy': 'market_maker',
                    'signal_type': 'bid',
                    'order_size': float(order_size),
                    'inventory': float(inventory),
                    'fair_price': float(price),
                    'volatility': float(self.volatility.get(symbol, 0))
                }
            )
            
            self.logger.debug(f"Placed bid order: {symbol} {order_size} @ {price}")
            
        except Exception as e:
            self.logger.error(f"Error placing bid order: {e}")
    
    async def _place_ask_order(self, symbol: str, price: Decimal) -> None:
        """Place ask order."""
        try:
            # Calculate order size based on inventory
            inventory = self.get_position(symbol)
            max_size = self.max_inventory + inventory
            
            if max_size <= 0:
                return
            
            order_size = min(self.order_size, max_size)
            
            # Generate signal
            await self.generate_signal(
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=order_size,
                price=price,
                order_type=OrderType.LIMIT,
                time_in_force=TimeInForce.GTC,
                confidence=0.9,
                metadata={
                    'strategy': 'market_maker',
                    'signal_type': 'ask',
                    'order_size': float(order_size),
                    'inventory': float(inventory),
                    'fair_price': float(price),
                    'volatility': float(self.volatility.get(symbol, 0))
                }
            )
            
            self.logger.debug(f"Placed ask order: {symbol} {order_size} @ {price}")
            
        except Exception as e:
            self.logger.error(f"Error placing ask order: {e}")
    
    async def _cancel_existing_orders(self, symbol: str) -> None:
        """Cancel existing orders for a symbol."""
        try:
            # This would typically cancel orders through the order manager
            # For now, we'll just clear the local tracking
            self.active_orders[symbol] = []
            
        except Exception as e:
            self.logger.error(f"Error canceling existing orders: {e}")
    
    async def _process_fill(self, fill) -> None:
        """Process trade fills for market maker strategy."""
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
            
            # Immediately refresh orders after fill
            await self._refresh_orders(symbol)
            
        except Exception as e:
            self.logger.error(f"Error processing fill: {e}")
    
    async def on_timer(self) -> None:
        """Handle timer events for market maker strategy."""
        try:
            # Refresh orders for all symbols
            for symbol in self.symbols:
                if time.time() - self.last_refresh[symbol] >= self.refresh_interval:
                    await self._refresh_orders(symbol)
            
        except Exception as e:
            self.logger.error(f"Error in timer: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get market maker strategy statistics."""
        stats = super().get_stats()
        
        # Add market maker-specific stats
        stats.update({
            'spread_pct': self.spread_pct,
            'inventory_bias': self.inventory_bias,
            'refresh_interval': self.refresh_interval,
            'max_inventory': self.max_inventory,
            'order_size': self.order_size,
            'current_volatility': {
                symbol: float(self.volatility[symbol])
                for symbol in self.symbols
            },
            'last_refresh': {
                symbol: self.last_refresh[symbol]
                for symbol in self.symbols
            },
            'active_orders': {
                symbol: len(self.active_orders[symbol])
                for symbol in self.symbols
            }
        })
        
        return stats
