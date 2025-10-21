"""
Pairs arbitrage strategy implementation.
Uses cointegration and statistical arbitrage for correlated pairs.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from collections import deque
import math

from .base import StrategyBase
from ..types import TradingSignal, MarketData, OrderSide, OrderType, TimeInForce


class PairsArbitrageStrategy(StrategyBase):
    """
    Pairs arbitrage strategy using cointegration and statistical arbitrage.
    
    Strategy Logic:
    1. Monitor price ratio between two correlated assets
    2. Fit cointegration model to detect mean reversion
    3. Generate signals when z-score exceeds threshold
    4. Use Kelly fraction for position sizing
    """
    
    def __init__(self, name: str, config: Dict[str, Any], symbols: List[str]):
        """Initialize pairs arbitrage strategy."""
        super().__init__(name, config, symbols)
        
        # Strategy parameters
        self.cointegration_window = config.get('cointegration_window', 100)
        self.z_score_threshold = config.get('z_score_threshold', 2.0)
        self.kelly_fraction = config.get('kelly_fraction', 0.1)
        self.max_position_ratio = config.get('max_position_ratio', 0.5)
        self.rebalance_interval = config.get('rebalance_interval', 300)  # 5 minutes
        
        # Pairs configuration
        self.pairs = self._configure_pairs(symbols)
        
        # Data storage
        self.price_ratios: Dict[str, deque] = {}
        self.cointegration_models: Dict[str, Dict[str, Any]] = {}
        self.z_scores: Dict[str, Decimal] = {}
        self.last_rebalance: Dict[str, float] = {}
        
        # Initialize data storage
        for pair_name in self.pairs:
            self.price_ratios[pair_name] = deque(maxlen=self.cointegration_window * 2)
            self.cointegration_models[pair_name] = {
                'alpha': Decimal('0'),
                'beta': Decimal('1'),
                'mu': Decimal('0'),
                'sigma': Decimal('1'),
                'theta': Decimal('0.1'),
                'is_valid': False
            }
            self.z_scores[pair_name] = Decimal('0')
            self.last_rebalance[pair_name] = 0
    
    def _configure_pairs(self, symbols: List[str]) -> Dict[str, Dict[str, str]]:
        """
        Configure trading pairs.
        
        Args:
            symbols: List of symbols to trade
            
        Returns:
            Dictionary of pair configurations
        """
        pairs = {}
        
        # Create pairs from symbols
        for i, symbol1 in enumerate(symbols):
            for symbol2 in symbols[i+1:]:
                pair_name = f"{symbol1}_{symbol2}"
                pairs[pair_name] = {
                    'asset1': symbol1,
                    'asset2': symbol2,
                    'ratio_symbol': f"{symbol1}/{symbol2}"
                }
        
        return pairs
    
    async def _process_market_data(self, market_data: MarketData) -> None:
        """Process market data for pairs arbitrage strategy."""
        try:
            symbol = market_data.symbol
            price = market_data.price
            
            # Update price ratios for all pairs containing this symbol
            for pair_name, pair_config in self.pairs.items():
                if symbol in [pair_config['asset1'], pair_config['asset2']]:
                    await self._update_price_ratio(pair_name, symbol, price)
            
        except Exception as e:
            self.logger.error(f"Error processing market data: {e}")
    
    async def _update_price_ratio(self, pair_name: str, symbol: str, price: Decimal) -> None:
        """Update price ratio for a pair."""
        try:
            pair_config = self.pairs[pair_name]
            
            # Get prices for both assets
            price1 = self._get_asset_price(pair_config['asset1'])
            price2 = self._get_asset_price(pair_config['asset2'])
            
            if price1 and price2 and price1 > 0 and price2 > 0:
                # Calculate price ratio
                ratio = price1 / price2
                self.price_ratios[pair_name].append(ratio)
                
                # Update cointegration model
                if len(self.price_ratios[pair_name]) >= self.cointegration_window:
                    await self._update_cointegration_model(pair_name)
                
                # Check for trading signals
                await self._check_arbitrage_signals(pair_name)
            
        except Exception as e:
            self.logger.error(f"Error updating price ratio: {e}")
    
    def _get_asset_price(self, symbol: str) -> Optional[Decimal]:
        """Get current price for an asset."""
        market_data = self.market_data.get(symbol)
        return market_data.price if market_data else None
    
    async def _update_cointegration_model(self, pair_name: str) -> None:
        """Update cointegration model for a pair."""
        try:
            ratios = list(self.price_ratios[pair_name])
            if len(ratios) < self.cointegration_window:
                return
            
            # Calculate log ratios
            log_ratios = [math.log(float(ratio)) for ratio in ratios[-self.cointegration_window:]]
            
            # Fit Ornstein-Uhlenbeck model
            model = self._fit_ornstein_uhlenbeck(log_ratios)
            
            if model:
                self.cointegration_models[pair_name] = model
                self.logger.debug(f"Updated cointegration model for {pair_name}: {model}")
            
        except Exception as e:
            self.logger.error(f"Error updating cointegration model: {e}")
    
    def _fit_ornstein_uhlenbeck(self, log_ratios: List[float]) -> Optional[Dict[str, Any]]:
        """
        Fit Ornstein-Uhlenbeck model to log ratios.
        
        dX_t = θ(μ - X_t) dt + σ dW_t
        
        Args:
            log_ratios: List of log price ratios
            
        Returns:
            Model parameters or None if fitting failed
        """
        try:
            if len(log_ratios) < 10:
                return None
            
            # Calculate mean and variance
            mean_ratio = sum(log_ratios) / len(log_ratios)
            variance = sum((x - mean_ratio) ** 2 for x in log_ratios) / len(log_ratios)
            std_dev = math.sqrt(variance)
            
            # Calculate theta (mean reversion speed)
            # This is a simplified calculation
            theta = 0.1  # Default value
            
            # Calculate mu (long-term mean)
            mu = mean_ratio
            
            # Calculate sigma (volatility)
            sigma = std_dev
            
            return {
                'alpha': Decimal('0'),
                'beta': Decimal('1'),
                'mu': Decimal(str(mu)),
                'sigma': Decimal(str(sigma)),
                'theta': Decimal(str(theta)),
                'is_valid': True
            }
            
        except Exception as e:
            self.logger.error(f"Error fitting Ornstein-Uhlenbeck model: {e}")
            return None
    
    async def _check_arbitrage_signals(self, pair_name: str) -> None:
        """Check for arbitrage trading signals."""
        try:
            model = self.cointegration_models[pair_name]
            if not model['is_valid']:
                return
            
            # Calculate z-score
            ratios = list(self.price_ratios[pair_name])
            if len(ratios) < 10:
                return
            
            current_ratio = ratios[-1]
            log_ratio = math.log(float(current_ratio))
            
            # Calculate z-score
            mu = float(model['mu'])
            sigma = float(model['sigma'])
            
            if sigma > 0:
                z_score = (log_ratio - mu) / sigma
                self.z_scores[pair_name] = Decimal(str(z_score))
                
                # Check for trading signals
                if abs(z_score) > self.z_score_threshold:
                    await self._generate_arbitrage_signal(pair_name, z_score)
            
        except Exception as e:
            self.logger.error(f"Error checking arbitrage signals: {e}")
    
    async def _generate_arbitrage_signal(self, pair_name: str, z_score: float) -> None:
        """Generate arbitrage trading signal."""
        try:
            pair_config = self.pairs[pair_name]
            asset1 = pair_config['asset1']
            asset2 = pair_config['asset2']
            
            # Determine trade direction based on z-score
            if z_score > self.z_score_threshold:
                # Ratio is too high, short asset1, long asset2
                await self._generate_pair_signal(pair_name, asset1, asset2, 'short_long')
            elif z_score < -self.z_score_threshold:
                # Ratio is too low, long asset1, short asset2
                await self._generate_pair_signal(pair_name, asset1, asset2, 'long_short')
            
        except Exception as e:
            self.logger.error(f"Error generating arbitrage signal: {e}")
    
    async def _generate_pair_signal(self, pair_name: str, asset1: str, asset2: str, direction: str) -> None:
        """Generate pair trading signal."""
        try:
            # Calculate position sizes
            size1, size2 = self._calculate_pair_sizes(pair_name, asset1, asset2, direction)
            
            if size1 <= 0 or size2 <= 0:
                return
            
            # Generate signals for both assets
            if direction == 'short_long':
                # Short asset1, long asset2
                await self.generate_signal(
                    symbol=asset1,
                    side=OrderSide.SELL,
                    quantity=size1,
                    order_type=OrderType.MARKET,
                    time_in_force=TimeInForce.IOC,
                    confidence=0.8,
                    metadata={
                        'strategy': 'pairs_arbitrage',
                        'signal_type': 'pair_trade',
                        'pair_name': pair_name,
                        'direction': direction,
                        'z_score': float(self.z_scores[pair_name]),
                        'asset2': asset2,
                        'size2': float(size2)
                    }
                )
                
                await self.generate_signal(
                    symbol=asset2,
                    side=OrderSide.BUY,
                    quantity=size2,
                    order_type=OrderType.MARKET,
                    time_in_force=TimeInForce.IOC,
                    confidence=0.8,
                    metadata={
                        'strategy': 'pairs_arbitrage',
                        'signal_type': 'pair_trade',
                        'pair_name': pair_name,
                        'direction': direction,
                        'z_score': float(self.z_scores[pair_name]),
                        'asset1': asset1,
                        'size1': float(size1)
                    }
                )
            
            elif direction == 'long_short':
                # Long asset1, short asset2
                await self.generate_signal(
                    symbol=asset1,
                    side=OrderSide.BUY,
                    quantity=size1,
                    order_type=OrderType.MARKET,
                    time_in_force=TimeInForce.IOC,
                    confidence=0.8,
                    metadata={
                        'strategy': 'pairs_arbitrage',
                        'signal_type': 'pair_trade',
                        'pair_name': pair_name,
                        'direction': direction,
                        'z_score': float(self.z_scores[pair_name]),
                        'asset2': asset2,
                        'size2': float(size2)
                    }
                )
                
                await self.generate_signal(
                    symbol=asset2,
                    side=OrderSide.SELL,
                    quantity=size2,
                    order_type=OrderType.MARKET,
                    time_in_force=TimeInForce.IOC,
                    confidence=0.8,
                    metadata={
                        'strategy': 'pairs_arbitrage',
                        'signal_type': 'pair_trade',
                        'pair_name': pair_name,
                        'direction': direction,
                        'z_score': float(self.z_scores[pair_name]),
                        'asset1': asset1,
                        'size1': float(size1)
                    }
                )
            
            self.logger.info(f"Generated pair signal: {pair_name} {direction} (z-score: {z_score:.2f})")
            
        except Exception as e:
            self.logger.error(f"Error generating pair signal: {e}")
    
    def _calculate_pair_sizes(self, pair_name: str, asset1: str, asset2: str, direction: str) -> Tuple[Decimal, Decimal]:
        """
        Calculate position sizes for pair trading.
        
        Args:
            pair_name: Pair name
            asset1: First asset
            asset2: Second asset
            direction: Trade direction
            
        Returns:
            Tuple of (size1, size2)
        """
        try:
            # Get current prices
            price1 = self._get_asset_price(asset1)
            price2 = self._get_asset_price(asset2)
            
            if not price1 or not price2:
                return Decimal('0'), Decimal('0')
            
            # Calculate base position size
            base_size = Decimal('100')  # Base position size
            
            # Apply Kelly fraction
            kelly_size = base_size * self.kelly_fraction
            
            # Apply position limits
            max_size = base_size * self.max_position_ratio
            size = min(kelly_size, max_size)
            
            # Calculate hedge ratio
            hedge_ratio = price1 / price2
            
            if direction == 'short_long':
                size1 = size
                size2 = size * hedge_ratio
            else:  # long_short
                size1 = size
                size2 = size / hedge_ratio
            
            return size1, size2
            
        except Exception as e:
            self.logger.error(f"Error calculating pair sizes: {e}")
            return Decimal('0'), Decimal('0')
    
    async def _process_fill(self, fill) -> None:
        """Process trade fills for pairs arbitrage strategy."""
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
        """Handle timer events for pairs arbitrage strategy."""
        try:
            # Check for rebalancing
            current_time = time.time()
            
            for pair_name in self.pairs:
                if current_time - self.last_rebalance[pair_name] >= self.rebalance_interval:
                    await self._rebalance_pair(pair_name)
                    self.last_rebalance[pair_name] = current_time
            
        except Exception as e:
            self.logger.error(f"Error in timer: {e}")
    
    async def _rebalance_pair(self, pair_name: str) -> None:
        """Rebalance a trading pair."""
        try:
            pair_config = self.pairs[pair_name]
            asset1 = pair_config['asset1']
            asset2 = pair_config['asset2']
            
            # Check current positions
            pos1 = self.get_position(asset1)
            pos2 = self.get_position(asset2)
            
            # If both positions are non-zero, check if we should close them
            if pos1 != 0 and pos2 != 0:
                # Check if z-score has returned to normal
                z_score = float(self.z_scores[pair_name])
                if abs(z_score) < self.z_score_threshold * 0.5:  # Close at half threshold
                    await self._close_pair_positions(pair_name, asset1, asset2)
            
        except Exception as e:
            self.logger.error(f"Error rebalancing pair: {e}")
    
    async def _close_pair_positions(self, pair_name: str, asset1: str, asset2: str) -> None:
        """Close pair positions."""
        try:
            pos1 = self.get_position(asset1)
            pos2 = self.get_position(asset2)
            
            if pos1 > 0:
                await self.generate_signal(
                    symbol=asset1,
                    side=OrderSide.SELL,
                    quantity=pos1,
                    order_type=OrderType.MARKET,
                    time_in_force=TimeInForce.IOC,
                    confidence=1.0,
                    metadata={
                        'strategy': 'pairs_arbitrage',
                        'signal_type': 'close_pair',
                        'pair_name': pair_name,
                        'reason': 'rebalance'
                    }
                )
            
            if pos2 > 0:
                await self.generate_signal(
                    symbol=asset2,
                    side=OrderSide.SELL,
                    quantity=pos2,
                    order_type=OrderType.MARKET,
                    time_in_force=TimeInForce.IOC,
                    confidence=1.0,
                    metadata={
                        'strategy': 'pairs_arbitrage',
                        'signal_type': 'close_pair',
                        'pair_name': pair_name,
                        'reason': 'rebalance'
                    }
                )
            
            self.logger.info(f"Closed pair positions: {pair_name}")
            
        except Exception as e:
            self.logger.error(f"Error closing pair positions: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pairs arbitrage strategy statistics."""
        stats = super().get_stats()
        
        # Add pairs arbitrage-specific stats
        stats.update({
            'cointegration_window': self.cointegration_window,
            'z_score_threshold': self.z_score_threshold,
            'kelly_fraction': self.kelly_fraction,
            'max_position_ratio': self.max_position_ratio,
            'rebalance_interval': self.rebalance_interval,
            'pairs': list(self.pairs.keys()),
            'current_z_scores': {
                pair_name: float(self.z_scores[pair_name])
                for pair_name in self.pairs
            },
            'cointegration_models': {
                pair_name: {
                    'mu': float(model['mu']),
                    'sigma': float(model['sigma']),
                    'theta': float(model['theta']),
                    'is_valid': model['is_valid']
                }
                for pair_name, model in self.cointegration_models.items()
            },
            'last_rebalance': {
                pair_name: self.last_rebalance[pair_name]
                for pair_name in self.pairs
            }
        })
        
        return stats
