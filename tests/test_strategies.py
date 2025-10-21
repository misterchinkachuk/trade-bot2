"""
Tests for trading strategies.
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime

from bot.strategies import ScalperStrategy, MarketMakerStrategy, PairsArbitrageStrategy
from bot.types import MarketData, OrderBook, OrderSide, OrderBookLevel


class TestScalperStrategy:
    """Test scalper strategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create scalper strategy instance."""
        config = {
            'ema_short': 5,
            'ema_long': 20,
            'obi_threshold': 0.25,
            'risk_fraction': 0.01,
            'stop_distance': 0.005
        }
        return ScalperStrategy("test_scalper", config, ["BTCUSDT"])
    
    @pytest.mark.asyncio
    async def test_initialization(self, strategy):
        """Test strategy initialization."""
        await strategy.initialize()
        assert strategy.is_initialized
        assert not strategy.is_enabled
    
    @pytest.mark.asyncio
    async def test_enable_disable(self, strategy):
        """Test enabling and disabling strategy."""
        await strategy.initialize()
        
        await strategy.enable()
        assert strategy.is_enabled
        
        await strategy.disable()
        assert not strategy.is_enabled
    
    @pytest.mark.asyncio
    async def test_market_data_processing(self, strategy):
        """Test market data processing."""
        await strategy.initialize()
        await strategy.enable()
        
        # Create test market data
        market_data = MarketData(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow(),
            price=Decimal("50000"),
            volume=Decimal("1.0"),
            side=OrderSide.BUY
        )
        
        # Process market data
        await strategy.on_market_data(market_data)
        
        # Check that price was stored
        assert "BTCUSDT" in strategy.price_history
        assert len(strategy.price_history["BTCUSDT"]) == 1
        assert strategy.price_history["BTCUSDT"][0] == Decimal("50000")
    
    @pytest.mark.asyncio
    async def test_orderbook_processing(self, strategy):
        """Test orderbook processing."""
        await strategy.initialize()
        await strategy.enable()
        
        # Create test orderbook
        orderbook = OrderBook(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow(),
            bids=[
                OrderBookLevel(price=Decimal("49999"), quantity=Decimal("1.0")),
                OrderBookLevel(price=Decimal("49998"), quantity=Decimal("2.0"))
            ],
            asks=[
                OrderBookLevel(price=Decimal("50001"), quantity=Decimal("1.5")),
                OrderBookLevel(price=Decimal("50002"), quantity=Decimal("2.5"))
            ],
            last_update_id=1
        )
        
        # Process orderbook
        await strategy.on_orderbook_update(orderbook)
        
        # Check that orderbook was stored
        assert "BTCUSDT" in strategy.orderbooks
        assert strategy.orderbooks["BTCUSDT"] == orderbook
    
    def test_ema_calculation(self, strategy):
        """Test EMA calculation."""
        prices = [Decimal("100"), Decimal("101"), Decimal("102"), Decimal("103"), Decimal("104")]
        ema = strategy.calculate_ema(prices, 3)
        assert ema > Decimal("0")
    
    def test_sma_calculation(self, strategy):
        """Test SMA calculation."""
        prices = [Decimal("100"), Decimal("101"), Decimal("102"), Decimal("103"), Decimal("104")]
        sma = strategy.calculate_sma(prices, 3)
        assert sma == Decimal("103")  # (102 + 103 + 104) / 3
    
    def test_rsi_calculation(self, strategy):
        """Test RSI calculation."""
        prices = [Decimal("100"), Decimal("101"), Decimal("102"), Decimal("103"), Decimal("104")]
        rsi = strategy.calculate_rsi(prices, 3)
        assert Decimal("0") <= rsi <= Decimal("100")


class TestMarketMakerStrategy:
    """Test market maker strategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create market maker strategy instance."""
        config = {
            'spread_pct': 0.001,
            'inventory_bias': 0.1,
            'refresh_interval': 5,
            'max_inventory': 1000,
            'order_size': 100
        }
        return MarketMakerStrategy("test_mm", config, ["BTCUSDT"])
    
    @pytest.mark.asyncio
    async def test_initialization(self, strategy):
        """Test strategy initialization."""
        await strategy.initialize()
        assert strategy.is_initialized
        assert not strategy.is_enabled
    
    @pytest.mark.asyncio
    async def test_volatility_calculation(self, strategy):
        """Test volatility calculation."""
        await strategy.initialize()
        
        # Add price history
        for price in [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]:
            strategy.price_history["BTCUSDT"].append(Decimal(str(price)))
        
        volatility = strategy._calculate_volatility("BTCUSDT")
        assert volatility >= Decimal("0")
    
    def test_fair_price_calculation(self, strategy):
        """Test fair price calculation."""
        # Create test orderbook
        orderbook = OrderBook(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow(),
            bids=[OrderBookLevel(price=Decimal("49999"), quantity=Decimal("1.0"))],
            asks=[OrderBookLevel(price=Decimal("50001"), quantity=Decimal("1.0"))],
            last_update_id=1
        )
        
        # Set position
        strategy.positions["BTCUSDT"] = Decimal("100")
        
        fair_price = strategy._calculate_fair_price("BTCUSDT", orderbook)
        assert fair_price > Decimal("0")


class TestPairsArbitrageStrategy:
    """Test pairs arbitrage strategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create pairs arbitrage strategy instance."""
        config = {
            'cointegration_window': 100,
            'z_score_threshold': 2.0,
            'kelly_fraction': 0.1,
            'max_position_ratio': 0.5
        }
        return PairsArbitrageStrategy("test_pairs", config, ["BTCUSDT", "ETHUSDT"])
    
    @pytest.mark.asyncio
    async def test_initialization(self, strategy):
        """Test strategy initialization."""
        await strategy.initialize()
        assert strategy.is_initialized
        assert not strategy.is_enabled
    
    def test_pair_configuration(self, strategy):
        """Test pair configuration."""
        assert "BTCUSDT_ETHUSDT" in strategy.pairs
        pair_config = strategy.pairs["BTCUSDT_ETHUSDT"]
        assert pair_config["asset1"] == "BTCUSDT"
        assert pair_config["asset2"] == "ETHUSDT"
    
    @pytest.mark.asyncio
    async def test_price_ratio_update(self, strategy):
        """Test price ratio update."""
        await strategy.initialize()
        
        # Set prices for both assets
        strategy.current_prices["BTCUSDT"] = Decimal("50000")
        strategy.current_prices["ETHUSDT"] = Decimal("3000")
        
        # Update price ratio
        await strategy._update_price_ratio("BTCUSDT_ETHUSDT", "BTCUSDT", Decimal("50000"))
        
        # Check that ratio was calculated
        assert "BTCUSDT_ETHUSDT" in strategy.price_ratios
        assert len(strategy.price_ratios["BTCUSDT_ETHUSDT"]) > 0
    
    def test_pair_size_calculation(self, strategy):
        """Test pair size calculation."""
        # Set prices
        strategy.current_prices["BTCUSDT"] = Decimal("50000")
        strategy.current_prices["ETHUSDT"] = Decimal("3000")
        
        size1, size2 = strategy._calculate_pair_sizes(
            "BTCUSDT_ETHUSDT", "BTCUSDT", "ETHUSDT", "short_long"
        )
        
        assert size1 > Decimal("0")
        assert size2 > Decimal("0")


@pytest.mark.asyncio
async def test_strategy_signal_generation():
    """Test signal generation across strategies."""
    # Test scalper signal generation
    scalper_config = {
        'ema_short': 5,
        'ema_long': 20,
        'obi_threshold': 0.25,
        'risk_fraction': 0.01,
        'stop_distance': 0.005
    }
    scalper = ScalperStrategy("test_scalper", scalper_config, ["BTCUSDT"])
    await scalper.initialize()
    
    # Mock signal handler
    signals = []
    async def mock_signal_handler(signal):
        signals.append(signal)
    
    scalper.on_signal = mock_signal_handler
    
    # Generate test signal
    await scalper.generate_signal(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        price=Decimal("50000"),
        confidence=0.8
    )
    
    assert len(signals) == 1
    assert signals[0].symbol == "BTCUSDT"
    assert signals[0].side == OrderSide.BUY
    assert signals[0].quantity == Decimal("0.1")


if __name__ == "__main__":
    pytest.main([__file__])
