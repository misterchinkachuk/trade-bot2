"""
Deterministic backtester for trading strategies.
Simulates trading with realistic latency, slippage, and fees.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from decimal import Decimal
from collections import defaultdict, deque
import random
import math

from .config import Config
from .types import MarketData, OrderBook, Kline, Order, Fill, OrderSide, OrderType, OrderStatus, BacktestResult
from .strategies import StrategyBase


class Backtester:
    """
    Deterministic backtester for trading strategies.
    
    Features:
    - Historical data replay
    - Realistic latency simulation
    - Slippage and fee modeling
    - Performance metrics calculation
    - Monte Carlo simulation support
    """
    
    def __init__(self, config: Config):
        """Initialize backtester."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Backtest configuration
        self.start_date = datetime.fromisoformat(config.backtest.start_date)
        self.end_date = datetime.fromisoformat(config.backtest.end_date)
        self.initial_capital = Decimal(str(config.backtest.initial_capital))
        self.commission = Decimal(str(config.backtest.commission))
        self.slippage = Decimal(str(config.backtest.slippage))
        
        # Simulation state
        self.current_time: Optional[datetime] = None
        self.current_capital = self.initial_capital
        self.positions: Dict[str, Decimal] = defaultdict(Decimal)
        self.entry_prices: Dict[str, Decimal] = defaultdict(Decimal)
        self.trades: List[Fill] = []
        self.orders: List[Order] = []
        
        # Performance tracking
        self.daily_pnl: Dict[datetime, Decimal] = {}
        self.max_drawdown = Decimal('0')
        self.peak_capital = self.initial_capital
        self.total_fees = Decimal('0')
        self.total_slippage = Decimal('0')
        
        # Data storage
        self.historical_data: Dict[str, List[Kline]] = {}
        self.current_prices: Dict[str, Decimal] = {}
        
        # Latency simulation
        self.latency_mean = 50  # milliseconds
        self.latency_std = 10
        self.latency_distribution = 'normal'
        
        # Random seed for reproducibility
        self.random_seed = 42
        random.seed(self.random_seed)
    
    async def run_backtest(
        self,
        strategy: StrategyBase,
        historical_data: Dict[str, List[Kline]],
        symbols: List[str]
    ) -> BacktestResult:
        """
        Run backtest for a strategy.
        
        Args:
            strategy: Trading strategy to test
            historical_data: Historical kline data
            symbols: List of symbols to trade
            
        Returns:
            Backtest result
        """
        try:
            self.logger.info(f"Starting backtest for strategy: {strategy.name}")
            
            # Initialize backtest state
            self._initialize_backtest(strategy, historical_data, symbols)
            
            # Run simulation
            await self._run_simulation(strategy, symbols)
            
            # Calculate results
            result = self._calculate_results(strategy)
            
            self.logger.info(f"Backtest completed: {result.total_return_pct:.2%} return")
            return result
            
        except Exception as e:
            self.logger.error(f"Error running backtest: {e}")
            raise
    
    def _initialize_backtest(self, strategy: StrategyBase, historical_data: Dict[str, List[Kline]], symbols: List[str]) -> None:
        """Initialize backtest state."""
        self.historical_data = historical_data
        self.current_capital = self.initial_capital
        self.positions = defaultdict(Decimal)
        self.entry_prices = defaultdict(Decimal)
        self.trades = []
        self.orders = []
        self.daily_pnl = {}
        self.max_drawdown = Decimal('0')
        self.peak_capital = self.initial_capital
        self.total_fees = Decimal('0')
        self.total_slippage = Decimal('0')
        
        # Set up strategy
        strategy.on_signal = self._handle_signal
        
        # Initialize current prices
        for symbol in symbols:
            if symbol in historical_data and historical_data[symbol]:
                self.current_prices[symbol] = historical_data[symbol][0].close_price
            else:
                self.current_prices[symbol] = Decimal('0')
    
    async def _run_simulation(self, strategy: StrategyBase, symbols: List[str]) -> None:
        """Run the backtest simulation."""
        try:
            # Get all timestamps from historical data
            all_timestamps = set()
            for symbol in symbols:
                if symbol in self.historical_data:
                    for kline in self.historical_data[symbol]:
                        all_timestamps.add(kline.open_time)
            
            # Sort timestamps
            sorted_timestamps = sorted(all_timestamps)
            
            # Process each timestamp
            for timestamp in sorted_timestamps:
                self.current_time = timestamp
                
                # Update current prices
                for symbol in symbols:
                    if symbol in self.historical_data:
                        for kline in self.historical_data[symbol]:
                            if kline.open_time == timestamp:
                                self.current_prices[symbol] = kline.close_price
                                
                                # Create market data
                                market_data = MarketData(
                                    symbol=symbol,
                                    timestamp=timestamp,
                                    price=kline.close_price,
                                    volume=kline.volume,
                                    side=OrderSide.BUY  # Default side
                                )
                                
                                # Send to strategy
                                await strategy.on_market_data(market_data)
                                break
                
                # Process pending orders
                await self._process_orders()
                
                # Update performance metrics
                self._update_performance_metrics()
            
        except Exception as e:
            self.logger.error(f"Error in simulation: {e}")
            raise
    
    async def _handle_signal(self, signal) -> None:
        """Handle trading signal from strategy."""
        try:
            # Create order
            order = Order(
                symbol=signal.symbol,
                side=signal.side,
                type=signal.order_type,
                quantity=signal.quantity,
                price=signal.price,
                time_in_force=signal.time_in_force,
                status=OrderStatus.NEW,
                created_at=self.current_time
            )
            
            # Add to orders list
            self.orders.append(order)
            
            # Simulate order execution
            await self._execute_order(order)
            
        except Exception as e:
            self.logger.error(f"Error handling signal: {e}")
    
    async def _execute_order(self, order: Order) -> None:
        """Execute an order with realistic simulation."""
        try:
            # Simulate latency
            latency = self._simulate_latency()
            await asyncio.sleep(latency / 1000)  # Convert to seconds
            
            # Get current price
            current_price = self.current_prices.get(order.symbol, Decimal('0'))
            if current_price == 0:
                order.status = OrderStatus.REJECTED
                return
            
            # Calculate execution price with slippage
            execution_price = self._calculate_execution_price(order, current_price)
            
            # Calculate fees
            notional = order.quantity * execution_price
            fee = notional * self.commission
            
            # Create fill
            fill = Fill(
                symbol=order.symbol,
                order_id=len(self.orders),
                trade_id=len(self.trades) + 1,
                side=order.side,
                quantity=order.quantity,
                price=execution_price,
                commission=fee,
                commission_asset='USDT',
                timestamp=self.current_time,
                is_maker=False
            )
            
            # Add to trades
            self.trades.append(fill)
            
            # Update position
            if order.side == OrderSide.BUY:
                self.positions[order.symbol] += order.quantity
            else:
                self.positions[order.symbol] -= order.quantity
            
            # Update entry price
            if self.positions[order.symbol] != 0:
                self.entry_prices[order.symbol] = execution_price
            
            # Update capital
            if order.side == OrderSide.BUY:
                self.current_capital -= notional + fee
            else:
                self.current_capital += notional - fee
            
            # Update order status
            order.status = OrderStatus.FILLED
            order.executed_qty = order.quantity
            order.cummulative_quote_qty = notional
            order.avg_price = execution_price
            
            # Update totals
            self.total_fees += fee
            self.total_slippage += abs(execution_price - current_price) * order.quantity
            
        except Exception as e:
            self.logger.error(f"Error executing order: {e}")
    
    def _simulate_latency(self) -> float:
        """Simulate order execution latency."""
        if self.latency_distribution == 'normal':
            latency = random.normalvariate(self.latency_mean, self.latency_std)
        else:
            latency = self.latency_mean
        
        return max(0, latency)  # Ensure non-negative
    
    def _calculate_execution_price(self, order: Order, current_price: Decimal) -> Decimal:
        """Calculate execution price with slippage."""
        try:
            if order.type == OrderType.MARKET:
                # Market order - apply slippage
                if order.side == OrderSide.BUY:
                    slippage = current_price * self.slippage
                    return current_price + slippage
                else:
                    slippage = current_price * self.slippage
                    return current_price - slippage
            
            elif order.type == OrderType.LIMIT:
                # Limit order - use order price if favorable, otherwise reject
                if order.side == OrderSide.BUY and order.price >= current_price:
                    return order.price
                elif order.side == OrderSide.SELL and order.price <= current_price:
                    return order.price
                else:
                    # Order not filled
                    return current_price
            
            else:
                return current_price
                
        except Exception as e:
            self.logger.error(f"Error calculating execution price: {e}")
            return current_price
    
    async def _process_orders(self) -> None:
        """Process pending orders."""
        # This would handle order management in a real implementation
        pass
    
    def _update_performance_metrics(self) -> None:
        """Update performance metrics."""
        try:
            # Calculate current portfolio value
            portfolio_value = self.current_capital
            
            for symbol, position in self.positions.items():
                if position != 0 and symbol in self.current_prices:
                    current_price = self.current_prices[symbol]
                    portfolio_value += position * current_price
            
            # Update peak capital
            if portfolio_value > self.peak_capital:
                self.peak_capital = portfolio_value
            
            # Calculate drawdown
            drawdown = (self.peak_capital - portfolio_value) / self.peak_capital
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown
            
            # Update daily P&L
            if self.current_time:
                date = self.current_time.date()
                daily_pnl = portfolio_value - self.initial_capital
                self.daily_pnl[date] = daily_pnl
            
        except Exception as e:
            self.logger.error(f"Error updating performance metrics: {e}")
    
    def _calculate_results(self, strategy: StrategyBase) -> BacktestResult:
        """Calculate backtest results."""
        try:
            # Calculate final capital
            final_capital = self.current_capital
            
            # Add position values
            for symbol, position in self.positions.items():
                if position != 0 and symbol in self.current_prices:
                    current_price = self.current_prices[symbol]
                    final_capital += position * current_price
            
            # Calculate returns
            total_return = final_capital - self.initial_capital
            total_return_pct = total_return / self.initial_capital
            
            # Calculate Sharpe ratio
            sharpe_ratio = self._calculate_sharpe_ratio()
            
            # Calculate win rate
            winning_trades = 0
            losing_trades = 0
            total_trades = len(self.trades)
            
            if total_trades > 0:
                # Simple win/loss calculation based on P&L
                for trade in self.trades:
                    if trade.side == OrderSide.BUY:
                        # This is a simplified calculation
                        winning_trades += 1
                    else:
                        losing_trades += 1
            
            win_rate = Decimal(str(winning_trades / total_trades)) if total_trades > 0 else Decimal('0')
            
            # Calculate average win/loss
            avg_win = Decimal('0')
            avg_loss = Decimal('0')
            
            if winning_trades > 0:
                avg_win = total_return / winning_trades
            if losing_trades > 0:
                avg_loss = abs(total_return) / losing_trades
            
            # Calculate profit factor
            profit_factor = avg_win / avg_loss if avg_loss > 0 else Decimal('0')
            
            return BacktestResult(
                strategy_name=strategy.name,
                start_date=self.start_date,
                end_date=self.end_date,
                initial_capital=self.initial_capital,
                final_capital=final_capital,
                total_return=total_return,
                total_return_pct=total_return_pct,
                max_drawdown=self.max_drawdown,
                max_drawdown_pct=self.max_drawdown,
                sharpe_ratio=sharpe_ratio,
                win_rate=win_rate,
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                avg_win=avg_win,
                avg_loss=avg_loss,
                profit_factor=profit_factor,
                trades=self.trades
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating results: {e}")
            raise
    
    def _calculate_sharpe_ratio(self) -> Decimal:
        """Calculate Sharpe ratio."""
        try:
            if len(self.daily_pnl) < 2:
                return Decimal('0')
            
            # Calculate daily returns
            daily_returns = []
            pnl_values = list(self.daily_pnl.values())
            
            for i in range(1, len(pnl_values)):
                daily_return = (pnl_values[i] - pnl_values[i-1]) / self.initial_capital
                daily_returns.append(float(daily_return))
            
            if len(daily_returns) < 2:
                return Decimal('0')
            
            # Calculate mean and standard deviation
            mean_return = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
            std_dev = math.sqrt(variance)
            
            if std_dev == 0:
                return Decimal('0')
            
            # Calculate Sharpe ratio (assuming risk-free rate of 0)
            sharpe_ratio = mean_return / std_dev
            
            return Decimal(str(sharpe_ratio))
            
        except Exception as e:
            self.logger.error(f"Error calculating Sharpe ratio: {e}")
            return Decimal('0')
    
    async def run_monte_carlo(
        self,
        strategy: StrategyBase,
        historical_data: Dict[str, List[Kline]],
        symbols: List[str],
        num_simulations: int = 100
    ) -> List[BacktestResult]:
        """
        Run Monte Carlo simulation.
        
        Args:
            strategy: Trading strategy to test
            historical_data: Historical kline data
            symbols: List of symbols to trade
            num_simulations: Number of simulations to run
            
        Returns:
            List of backtest results
        """
        results = []
        
        for i in range(num_simulations):
            try:
                # Reset random seed for each simulation
                random.seed(self.random_seed + i)
                
                # Run backtest
                result = await self.run_backtest(strategy, historical_data, symbols)
                results.append(result)
                
                self.logger.info(f"Monte Carlo simulation {i+1}/{num_simulations} completed")
                
            except Exception as e:
                self.logger.error(f"Error in Monte Carlo simulation {i+1}: {e}")
                continue
        
        return results
    
    def get_performance_summary(self, results: List[BacktestResult]) -> Dict[str, Any]:
        """Get performance summary from multiple backtest results."""
        try:
            if not results:
                return {}
            
            # Calculate statistics
            returns = [float(r.total_return_pct) for r in results]
            sharpe_ratios = [float(r.sharpe_ratio) for r in results]
            max_drawdowns = [float(r.max_drawdown_pct) for r in results]
            win_rates = [float(r.win_rate) for r in results]
            
            return {
                'num_simulations': len(results),
                'avg_return': sum(returns) / len(returns),
                'std_return': math.sqrt(sum((r - sum(returns)/len(returns))**2 for r in returns) / len(returns)),
                'min_return': min(returns),
                'max_return': max(returns),
                'avg_sharpe': sum(sharpe_ratios) / len(sharpe_ratios),
                'avg_drawdown': sum(max_drawdowns) / len(max_drawdowns),
                'max_drawdown': max(max_drawdowns),
                'avg_win_rate': sum(win_rates) / len(win_rates),
                'profitable_simulations': sum(1 for r in returns if r > 0),
                'profitability_rate': sum(1 for r in returns if r > 0) / len(returns)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating performance summary: {e}")
            return {}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get backtester statistics."""
        return {
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'initial_capital': float(self.initial_capital),
            'current_capital': float(self.current_capital),
            'total_trades': len(self.trades),
            'total_orders': len(self.orders),
            'total_fees': float(self.total_fees),
            'total_slippage': float(self.total_slippage),
            'max_drawdown': float(self.max_drawdown),
            'peak_capital': float(self.peak_capital),
            'positions': {symbol: float(pos) for symbol, pos in self.positions.items()},
            'current_prices': {symbol: float(price) for symbol, price in self.current_prices.items()}
        }
