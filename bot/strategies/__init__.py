"""
Trading strategies module.
Contains base strategy class and implementations.
"""

from .base import StrategyBase
from .scalper import ScalperStrategy
from .market_maker import MarketMakerStrategy
from .pairs_arbitrage import PairsArbitrageStrategy

__all__ = [
    "StrategyBase",
    "ScalperStrategy",
    "MarketMakerStrategy", 
    "PairsArbitrageStrategy",
]
