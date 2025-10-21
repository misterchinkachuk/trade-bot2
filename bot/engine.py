"""
Main trading engine that orchestrates all components.
Handles the asyncio event loop and coordinates between strategies, execution, and risk management.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path

from .config import Config, load_config
from .types import TradingSignal, RiskEvent, Order, Fill, Position
from .data_ingest import MarketDataIngester
from .execution import OrderManager
from .risk import RiskManager
from .strategies import StrategyBase
from .accounting import AccountingManager
from .monitoring import MonitoringManager


class TradingEngine:
    """
    Main trading engine that coordinates all components.
    
    The engine runs in an asyncio event loop and manages:
    - Market data ingestion from WebSocket streams
    - Strategy execution and signal generation
    - Order management and execution
    - Risk management and position monitoring
    - Accounting and P&L tracking
    - Monitoring and alerting
    """
    
    def __init__(self, config: Config):
        """Initialize the trading engine with configuration."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Core components
        self.data_ingester: Optional[MarketDataIngester] = None
        self.order_manager: Optional[OrderManager] = None
        self.risk_manager: Optional[RiskManager] = None
        self.accounting_manager: Optional[AccountingManager] = None
        self.monitoring_manager: Optional[MonitoringManager] = None
        
        # Strategy management
        self.strategies: Dict[str, StrategyBase] = {}
        self.active_strategies: Set[str] = set()
        
        # State management
        self.is_running = False
        self.is_initialized = False
        self.shutdown_event = asyncio.Event()
        
        # Performance tracking
        self.start_time: Optional[datetime] = None
        self.total_signals = 0
        self.total_orders = 0
        self.total_fills = 0
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def initialize(self) -> None:
        """Initialize all components and establish connections."""
        try:
            self.logger.info("Initializing trading engine...")
            
            # Initialize core components
            self.data_ingester = MarketDataIngester(self.config)
            self.order_manager = OrderManager(self.config)
            self.risk_manager = RiskManager(self.config)
            self.accounting_manager = AccountingManager(self.config)
            self.monitoring_manager = MonitoringManager(self.config)
            
            # Initialize components
            await self.data_ingester.initialize()
            await self.order_manager.initialize()
            await self.risk_manager.initialize()
            await self.accounting_manager.initialize()
            await self.monitoring_manager.initialize()
            
            # Load and initialize strategies
            await self._load_strategies()
            
            # Setup event handlers
            self._setup_event_handlers()
            
            self.is_initialized = True
            self.logger.info("Trading engine initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize trading engine: {e}")
            raise
    
    async def _load_strategies(self) -> None:
        """Load and initialize trading strategies."""
        from .strategies.scalper import ScalperStrategy
        from .strategies.market_maker import MarketMakerStrategy
        from .strategies.pairs_arbitrage import PairsArbitrageStrategy
        
        strategy_classes = {
            'scalper': ScalperStrategy,
            'market_maker': MarketMakerStrategy,
            'pairs_arbitrage': PairsArbitrageStrategy,
        }
        
        for strategy_name, strategy_config in self.config.strategies.items():
            if not strategy_config.enabled:
                continue
                
            if strategy_name not in strategy_classes:
                self.logger.warning(f"Unknown strategy: {strategy_name}")
                continue
            
            try:
                strategy_class = strategy_classes[strategy_name]
                strategy = strategy_class(
                    name=strategy_name,
                    config=strategy_config.params,
                    symbols=self.config.trading.symbols
                )
                
                await strategy.initialize()
                self.strategies[strategy_name] = strategy
                self.active_strategies.add(strategy_name)
                
                self.logger.info(f"Loaded strategy: {strategy_name}")
                
            except Exception as e:
                self.logger.error(f"Failed to load strategy {strategy_name}: {e}")
    
    def _setup_event_handlers(self) -> None:
        """Setup event handlers for inter-component communication."""
        # Market data events
        if self.data_ingester:
            self.data_ingester.on_market_data = self._on_market_data
            self.data_ingester.on_orderbook_update = self._on_orderbook_update
            self.data_ingester.on_kline_update = self._on_kline_update
        
        # Order events
        if self.order_manager:
            self.order_manager.on_order_update = self._on_order_update
            self.order_manager.on_fill = self._on_fill
        
        # Risk events
        if self.risk_manager:
            self.risk_manager.on_risk_event = self._on_risk_event
    
    async def _on_market_data(self, market_data) -> None:
        """Handle incoming market data."""
        try:
            # Update risk manager with latest prices
            if self.risk_manager:
                await self.risk_manager.update_market_data(market_data)
            
            # Send to active strategies
            for strategy_name in self.active_strategies:
                strategy = self.strategies.get(strategy_name)
                if strategy:
                    try:
                        await strategy.on_market_data(market_data)
                    except Exception as e:
                        self.logger.error(f"Error in strategy {strategy_name}: {e}")
            
            # Update monitoring
            if self.monitoring_manager:
                await self.monitoring_manager.record_market_data(market_data)
                
        except Exception as e:
            self.logger.error(f"Error handling market data: {e}")
    
    async def _on_orderbook_update(self, orderbook) -> None:
        """Handle orderbook updates."""
        try:
            # Send to strategies that need orderbook data
            for strategy_name in self.active_strategies:
                strategy = self.strategies.get(strategy_name)
                if strategy and hasattr(strategy, 'on_orderbook_update'):
                    try:
                        await strategy.on_orderbook_update(orderbook)
                    except Exception as e:
                        self.logger.error(f"Error in strategy {strategy_name} orderbook handler: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error handling orderbook update: {e}")
    
    async def _on_kline_update(self, kline) -> None:
        """Handle kline updates."""
        try:
            # Send to strategies that need kline data
            for strategy_name in self.active_strategies:
                strategy = self.strategies.get(strategy_name)
                if strategy and hasattr(strategy, 'on_kline_update'):
                    try:
                        await strategy.on_kline_update(kline)
                    except Exception as e:
                        self.logger.error(f"Error in strategy {strategy_name} kline handler: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error handling kline update: {e}")
    
    async def _on_order_update(self, order: Order) -> None:
        """Handle order updates."""
        try:
            # Update accounting
            if self.accounting_manager:
                await self.accounting_manager.update_order(order)
            
            # Update monitoring
            if self.monitoring_manager:
                await self.monitoring_manager.record_order_update(order)
            
            self.total_orders += 1
            
        except Exception as e:
            self.logger.error(f"Error handling order update: {e}")
    
    async def _on_fill(self, fill: Fill) -> None:
        """Handle trade fills."""
        try:
            # Update accounting
            if self.accounting_manager:
                await self.accounting_manager.record_fill(fill)
            
            # Update risk manager
            if self.risk_manager:
                await self.risk_manager.update_position(fill)
            
            # Notify strategies
            for strategy_name in self.active_strategies:
                strategy = self.strategies.get(strategy_name)
                if strategy and hasattr(strategy, 'on_fill'):
                    try:
                        await strategy.on_fill(fill)
                    except Exception as e:
                        self.logger.error(f"Error in strategy {strategy_name} fill handler: {e}")
            
            # Update monitoring
            if self.monitoring_manager:
                await self.monitoring_manager.record_fill(fill)
            
            self.total_fills += 1
            
        except Exception as e:
            self.logger.error(f"Error handling fill: {e}")
    
    async def _on_risk_event(self, risk_event: RiskEvent) -> None:
        """Handle risk management events."""
        try:
            self.logger.warning(f"Risk event: {risk_event.message}")
            
            # Update monitoring
            if self.monitoring_manager:
                await self.monitoring_manager.record_risk_event(risk_event)
            
            # Handle critical risk events
            if risk_event.severity == "CRITICAL":
                self.logger.critical("Critical risk event detected, shutting down strategies")
                await self._disable_all_strategies()
                
        except Exception as e:
            self.logger.error(f"Error handling risk event: {e}")
    
    async def _disable_all_strategies(self) -> None:
        """Disable all active strategies."""
        for strategy_name in list(self.active_strategies):
            await self.disable_strategy(strategy_name)
    
    async def run(self) -> None:
        """Main run loop."""
        if not self.is_initialized:
            await self.initialize()
        
        self.logger.info("Starting trading engine...")
        self.is_running = True
        self.start_time = datetime.utcnow()
        
        try:
            # Start all components
            tasks = []
            
            if self.data_ingester:
                tasks.append(asyncio.create_task(self.data_ingester.start()))
            
            if self.monitoring_manager:
                tasks.append(asyncio.create_task(self.monitoring_manager.start()))
            
            # Start strategy timers
            for strategy_name in self.active_strategies:
                strategy = self.strategies.get(strategy_name)
                if strategy and hasattr(strategy, 'start_timer'):
                    tasks.append(asyncio.create_task(strategy.start_timer()))
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except Exception as e:
            self.logger.error(f"Error in main run loop: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the trading engine."""
        if not self.is_running:
            return
        
        self.logger.info("Shutting down trading engine...")
        self.is_running = False
        
        try:
            # Cancel all open orders
            if self.order_manager:
                await self.order_manager.cancel_all_orders()
            
            # Stop all strategies
            for strategy_name in list(self.active_strategies):
                await self.disable_strategy(strategy_name)
            
            # Stop components
            if self.data_ingester:
                await self.data_ingester.stop()
            
            if self.monitoring_manager:
                await self.monitoring_manager.stop()
            
            # Close connections
            if self.order_manager:
                await self.order_manager.close()
            
            if self.accounting_manager:
                await self.accounting_manager.close()
            
            self.logger.info("Trading engine shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        finally:
            self.shutdown_event.set()
    
    async def submit_signal(self, signal: TradingSignal) -> None:
        """Submit a trading signal from a strategy."""
        try:
            # Risk check
            if self.risk_manager:
                risk_approved = await self.risk_manager.check_signal(signal)
                if not risk_approved:
                    self.logger.warning(f"Signal rejected by risk manager: {signal}")
                    return
            
            # Submit to order manager
            if self.order_manager:
                await self.order_manager.submit_signal(signal)
            
            self.total_signals += 1
            
        except Exception as e:
            self.logger.error(f"Error submitting signal: {e}")
    
    async def enable_strategy(self, strategy_name: str) -> bool:
        """Enable a strategy."""
        if strategy_name not in self.strategies:
            self.logger.error(f"Strategy not found: {strategy_name}")
            return False
        
        if strategy_name in self.active_strategies:
            self.logger.warning(f"Strategy already enabled: {strategy_name}")
            return True
        
        try:
            strategy = self.strategies[strategy_name]
            await strategy.enable()
            self.active_strategies.add(strategy_name)
            self.logger.info(f"Enabled strategy: {strategy_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to enable strategy {strategy_name}: {e}")
            return False
    
    async def disable_strategy(self, strategy_name: str) -> bool:
        """Disable a strategy."""
        if strategy_name not in self.active_strategies:
            self.logger.warning(f"Strategy not active: {strategy_name}")
            return True
        
        try:
            strategy = self.strategies.get(strategy_name)
            if strategy:
                await strategy.disable()
            
            self.active_strategies.remove(strategy_name)
            self.logger.info(f"Disabled strategy: {strategy_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to disable strategy {strategy_name}: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get current engine status."""
        return {
            "is_running": self.is_running,
            "is_initialized": self.is_initialized,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "active_strategies": list(self.active_strategies),
            "total_signals": self.total_signals,
            "total_orders": self.total_orders,
            "total_fills": self.total_fills,
        }


async def main():
    """Main entry point for the trading engine."""
    # Load configuration
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = load_config(config_path)
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config.logging.level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.logging.file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Create and run engine
    engine = TradingEngine(config)
    
    try:
        await engine.run()
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
