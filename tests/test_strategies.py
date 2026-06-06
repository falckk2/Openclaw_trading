"""Tests for strategies module."""

import pytest
from datetime import datetime, timedelta

from src.strategies.base import Strategy, StrategyConfig
from src.strategies.signal import Signal
from src.strategies.manager import StrategyManager
from src.strategies.ml.grid import GridStrategy, GridConfig
from src.strategies.ml.mean_reversion import MeanReversionStrategy, MeanReversionConfig
from src.data.dataclasses import Candle


class TestSignal:
    """Tests for Signal dataclass."""

    def test_hold_signal(self):
        """Signal.hold() creates correct hold signal."""
        signal = Signal.hold("test_strategy", "BTCUSDT", 0.5)
        assert signal.action == "hold"
        assert signal.strategy_name == "test_strategy"
        assert signal.symbol == "BTCUSDT"
        assert signal.confidence == 0.5


class TestGridStrategy:
    """Tests for GridStrategy."""

    def test_grid_config(self):
        config = GridConfig(
            symbol="BTCUSDT",
            grid_size=5,
            price_range_pct=0.05,
            order_quantity=0.001,
        )
        assert config.grid_size == 5
        assert config.price_range_pct == 0.05

    @pytest.mark.asyncio
    async def test_grid_generate_signal(self):
        """Grid strategy should generate signals near boundaries."""
        config = GridConfig(
            symbol="BTCUSDT",
            grid_size=5,
            price_range_pct=0.05,
            order_quantity=0.001,
            center_price=50000.0,
        )
        strategy = GridStrategy(config)
        assert strategy.validate()

        # Create candles
        base_price = 50000.0
        candles = [
            Candle(
                timestamp=datetime.utcnow() - timedelta(hours=i),
                open=base_price + i * 10,
                high=base_price + i * 10 + 100,
                low=base_price + i * 10 - 100,
                close=base_price + i * 10,
                volume=1000,
            )
            for i in range(10)
        ]

        signal = await strategy.generate_signal(candles, position=None)
        assert signal is not None  # Should always return a signal (buy/sell/hold)


class TestMeanReversionStrategy:
    """Tests for MeanReversionStrategy."""

    def test_mean_reversion_config(self):
        config = MeanReversionConfig(
            symbol="BTCUSDT",
            window=20,
            std_multiplier=2.0,
        )
        assert config.window == 20

    @pytest.mark.asyncio
    async def test_hold_when_insufficient_data(self):
        """Strategy returns hold when not enough data."""
        config = MeanReversionConfig(symbol="BTCUSDT", window=20)
        strategy = MeanReversionStrategy(config)

        candles = [
            Candle(
                timestamp=datetime.utcnow() - timedelta(hours=i),
                open=50000 + i * 10,
                high=50100 + i * 10,
                low=49900 + i * 10,
                close=50000 + i * 10,
                volume=1000,
            )
            for i in range(5)
        ]

        signal = await strategy.generate_signal(candles, None)
        assert signal.action == "hold"
        assert signal.confidence == 0.0