"""
Binance Trading Bot - Core Module

A production-ready algorithmic trading system for Binance with modular architecture,
comprehensive risk management, and real-time market data processing.
"""

__version__ = "1.0.0"
__author__ = "Trading Bot Team"

from .engine import TradingEngine
from .strategies import StrategyBase
from .execution import OrderManager
from .risk import RiskManager
from .data_ingest import MarketDataIngester

__all__ = [
    "TradingEngine",
    "StrategyBase", 
    "OrderManager",
    "RiskManager",
    "MarketDataIngester",
]
