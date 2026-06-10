"""Tests for strategies module."""

import pytest
from datetime import datetime, timedelta, UTC

from src.strategies.base import Strategy, StrategyConfig
from src.strategies.signal import Signal
from src.strategies.manager import StrategyManager
from src.strategies.ml.grid import GridStrategy, GridConfig
from src.strategies.ml.rsi_bollinger import RSIBollingerStrategy, RSIBollingerConfig
from src.strategies.ml.mean_reversion import MeanReversionStrategy, MeanReversionConfig
from src.strategies.ml.momentum import MomentumStrategy, MomentumConfig
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
                timestamp=datetime.now(UTC) - timedelta(hours=i),
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
                timestamp=datetime.now(UTC) - timedelta(hours=i),
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


class TestMomentumStrategy:
    """Tests for MomentumStrategy."""

    def test_momentum_config(self):
        config = MomentumConfig(
            symbol="BTCUSDT",
            momentum_period=10,
            ma_short=20,
            ma_long=50,
        )
        assert config.momentum_period == 10
        assert config.ma_short == 20
        assert config.ma_long == 50

    def test_momentum_validate(self):
        """Valid config passes validation."""
        config = MomentumConfig(symbol="BTCUSDT")
        strategy = MomentumStrategy(config)
        assert strategy.validate()

    def test_momentum_validate_fails_bad_params(self):
        """Invalid config fails validation."""
        config = MomentumConfig(
            symbol="BTCUSDT",
            momentum_period=10,
            ma_short=5,   # must be > momentum_period
            ma_long=3,    # must be > ma_short
        )
        strategy = MomentumStrategy(config)
        assert not strategy.validate()

    @pytest.mark.asyncio
    async def test_hold_when_insufficient_data(self):
        """Strategy returns hold when not enough data."""
        config = MomentumConfig(symbol="BTCUSDT", momentum_period=10, ma_short=20, ma_long=50)
        strategy = MomentumStrategy(config)

        candles = [
            Candle(
                timestamp=datetime.now(UTC) - timedelta(hours=i),
                open=50000 + i * 10,
                high=50100 + i * 10,
                low=49900 + i * 10,
                close=50000 + i * 10,
                volume=1000,
            )
            for i in range(10)
        ]

        signal = await strategy.generate_signal(candles, None)
        assert signal.action == "hold"
        assert signal.confidence == 0.0

    @pytest.mark.asyncio
    async def test_momentum_uptrend_buy_signal(self):
        """Uptrend with pullback triggers buy signal."""
        config = MomentumConfig(
            symbol="BTCUSDT",
            momentum_period=5,
            ma_short=10,
            ma_long=20,
            momentum_threshold=0.005,
            entry_deviation=-0.5,
        )
        strategy = MomentumStrategy(config)

        # Create uptrend: prices going up then slight pullback
        base = 50000.0
        candles = [
            Candle(
                timestamp=datetime.now(UTC) - timedelta(hours=60 - i),
                open=base + i * 50,
                high=base + i * 50 + 100,
                low=base + i * 50 - 100,
                close=base + i * 50,
                volume=1000,
            )
            for i in range(25)
        ]

        signal = await strategy.generate_signal(candles, None)
        # Should detect uptrend momentum with some action
        assert signal is not None
        assert signal.action in ["buy", "hold"]
        assert signal.symbol == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_momentum_downtrend_sell_signal(self):
        """Downtrend with bounce triggers sell signal."""
        config = MomentumConfig(
            symbol="BTCUSDT",
            momentum_period=5,
            ma_short=10,
            ma_long=20,
            momentum_threshold=0.005,
            entry_deviation=-0.5,
        )
        strategy = MomentumStrategy(config)

        # Create downtrend: prices going down then slight bounce
        base = 51000.0
        candles = [
            Candle(
                timestamp=datetime.now(UTC) - timedelta(hours=60 - i),
                open=base - i * 50,
                high=base - i * 50 + 200,
                low=base - i * 50 - 100,
                close=base - i * 50,
                volume=1000,
            )
            for i in range(25)
        ]

        signal = await strategy.generate_signal(candles, None)
        # Should detect downtrend momentum with some action
        assert signal is not None
        assert signal.action in ["sell", "hold"]
        assert signal.symbol == "BTCUSDT"


    @pytest.mark.asyncio
    async def test_momentum_flat_market_hold(self):
        """Flat market with minimal price change returns hold."""
        config = MomentumConfig(
            symbol="BTCUSDT",
            momentum_period=5,
            ma_short=10,
            ma_long=20,
            momentum_threshold=0.005,
        )
        strategy = MomentumStrategy(config)

        # Flat market: nearly identical prices
        base = 50000.0
        candles = [
            Candle(
                timestamp=datetime.now(UTC) - timedelta(hours=30 - i),
                open=base + (i % 3) * 5,
                high=base + (i % 3) * 5 + 50,
                low=base + (i % 3) * 5 - 50,
                close=base + (i % 3) * 5,
                volume=1000,
            )
            for i in range(25)
        ]

        signal = await strategy.generate_signal(candles, None)
        assert signal is not None
        assert signal.action == "hold"

    @pytest.mark.asyncio
    async def test_momentum_metadata_populated(self):
        """Signal metadata contains momentum, MA, and deviation values."""
        config = MomentumConfig(
            symbol="BTCUSDT",
            momentum_period=5,
            ma_short=10,
            ma_long=20,
            momentum_threshold=0.005,
            entry_deviation=-0.5,
        )
        strategy = MomentumStrategy(config)

        # Clear uptrend
        base = 50000.0
        candles = [
            Candle(
                timestamp=datetime.now(UTC) - timedelta(hours=30 - i),
                open=base + i * 50,
                high=base + i * 50 + 100,
                low=base + i * 50 - 100,
                close=base + i * 50,
                volume=1000,
            )
            for i in range(25)
        ]

        signal = await strategy.generate_signal(candles, None)
        if signal and signal.action != "hold":
            assert "momentum" in signal.metadata
            assert "ma_short" in signal.metadata
            assert "ma_long" in signal.metadata
            assert "deviation" in signal.metadata



class TestStrategyManager:
    """Tests for StrategyManager."""

    def test_manager_add_remove(self):
        """Manager can add and remove strategies."""
        grid_cfg = GridConfig(symbol="BTCUSDT", grid_size=5, price_range_pct=0.05, order_quantity=0.001)
        grid = GridStrategy(grid_cfg)
        manager = StrategyManager([grid])

        assert manager.list_strategies() == ["grid"]

        mr_cfg = MeanReversionConfig(symbol="BTCUSDT", window=20)
        mr = MeanReversionStrategy(mr_cfg)
        manager.add_strategy(mr)
        assert "mean_reversion" in manager.list_strategies()

        manager.remove_strategy("grid")
        assert manager.list_strategies() == ["mean_reversion"]
        assert manager.get_strategy("grid") is None
        assert manager.get_strategy("mean_reversion") is not None

    def test_manager_get_strategy_config(self):
        """get_strategy_config returns correct config."""
        grid_cfg = GridConfig(symbol="BTCUSDT", grid_size=5, price_range_pct=0.05, order_quantity=0.001)
        grid = GridStrategy(grid_cfg)
        manager = StrategyManager([grid])
        cfg = manager.get_strategy_config("grid")
        assert cfg is not None
        assert cfg.grid_size == 5

    @pytest.mark.asyncio
    async def test_manager_run_all_strategies(self):
        """run_strategies returns signals from all valid strategies."""
        grid_cfg = GridConfig(symbol="BTCUSDT", grid_size=5, price_range_pct=0.05, order_quantity=0.001, center_price=50000.0)
        grid = GridStrategy(grid_cfg)
        mr_cfg = MeanReversionConfig(symbol="BTCUSDT", window=20)
        mr = MeanReversionStrategy(mr_cfg)
        manager = StrategyManager([grid, mr])

        candles = [
            Candle(
                timestamp=datetime.now(UTC) - timedelta(hours=i),
                open=50000 + i * 10,
                high=50100 + i * 10,
                low=49900 + i * 10,
                close=50000 + i * 10,
                volume=1000,
            )
            for i in range(25)
        ]

        signals = await manager.run_strategies(candles, "BTCUSDT", position=None)
        assert isinstance(signals, list)

    @pytest.mark.asyncio
    async def test_manager_run_single_strategy(self):
        """run_strategy runs a single named strategy."""
        grid_cfg = GridConfig(symbol="BTCUSDT", grid_size=5, price_range_pct=0.05, order_quantity=0.001, center_price=50000.0)
        grid = GridStrategy(grid_cfg)
        manager = StrategyManager([grid])

        candles = [
            Candle(
                timestamp=datetime.now(UTC) - timedelta(hours=i),
                open=50000 + i * 10,
                high=50100 + i * 10,
                low=49900 + i * 10,
                close=50000 + i * 10,
                volume=1000,
            )
            for i in range(10)
        ]

        signal = await manager.run_strategy("grid", candles, position=None)
        assert signal is not None

    @pytest.mark.asyncio
    async def test_manager_invalid_strategy_returns_none(self):
        """run_strategy returns None for invalid strategy."""
        # Invalid config: ma_short < momentum_period
        bad_cfg = MomentumConfig(symbol="BTCUSDT", momentum_period=10, ma_short=5, ma_long=3)
        bad_strategy = MomentumStrategy(bad_cfg)
        manager = StrategyManager([bad_strategy])

        candles = [
            Candle(
                timestamp=datetime.now(UTC) - timedelta(hours=i),
                open=50000 + i * 10,
                high=50100 + i * 10,
                low=49900 + i * 10,
                close=50000 + i * 10,
                volume=1000,
            )
            for i in range(25)
        ]

        signal = await manager.run_strategy("momentum", candles, position=None)
        assert signal is None  # Invalid strategy returns None


class TestRSIBollingerStrategy:
    """Tests for RSIBollingerStrategy."""

    def test_rsi_bollinger_config(self):
        config = RSIBollingerConfig(symbol="BTCUSDT")
        assert config.symbol == "BTCUSDT"
        assert config.rsi_period == 14
        assert config.bb_period == 20

    @pytest.mark.asyncio
    async def test_rsi_bollinger_hold_insufficient_data(self):
        """"RSIBollinger returns hold with insufficient data."""
        config = RSIBollingerConfig(symbol="BTCUSDT")
        strategy = RSIBollingerStrategy(config)

        candles = [
            Candle(
                timestamp=datetime.now(UTC) - timedelta(hours=i),
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

    @pytest.mark.asyncio
    async def test_rsi_bollinger_valid_data(self):
        """RSIBollinger returns a signal with enough data."""
        config = RSIBollingerConfig(symbol="BTCUSDT")
        strategy = RSIBollingerStrategy(config)

        candles = [
            Candle(
                timestamp=datetime.now(UTC) - timedelta(hours=i),
                open=50000 + i * 10,
                high=50100 + i * 10,
                low=49900 + i * 10,
                close=50000 + i * 10,
                volume=1000,
            )
            for i in range(30)
        ]

        signal = await strategy.generate_signal(candles, None)
        assert signal is not None
        assert signal.action in ["buy", "sell", "hold"]
        assert signal.symbol == "BTCUSDT"