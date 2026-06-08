"""Tests for strategy performance attribution."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.paper_trading.simulator import PaperTradingEngine
from src.paper_trading.order_tracker import SimulatedTrade
from src.logging.performance_logger import PerformanceLogger
from src.data.dataclasses import Ticker


class MockExchange:
    """Minimal mock exchange for paper trading tests."""

    def __init__(self):
        self._prices = {}

    async def get_ticker(self, symbol: str) -> Ticker:
        price = self._prices.get(symbol, 100.0)
        return Ticker(
            symbol=symbol,
            last=price,
            bid=price - 0.01,
            ask=price + 0.01,
            volume=1000.0,
            timestamp=datetime.utcnow(),
        )

    def set_price(self, symbol: str, price: float):
        self._prices[symbol] = price


class TestStrategyAttribution:
    """Test that trades are correctly attributed to strategies."""

    @pytest.fixture
    def exchange(self):
        return MockExchange()

    @pytest.fixture
    def engine(self, exchange):
        return PaperTradingEngine(exchange, initial_balance=10000.0)

    @pytest.mark.asyncio
    async def test_trade_records_strategy_name(self, engine, exchange):
        """A trade should record which strategy opened it."""
        symbol = "BTC-USDT"

        # Open position with strategy attribution
        await engine.open_position(symbol, "long", 1.0, strategy_name="MeanReversionStrategy")

        # Close position
        exchange.set_price(symbol, 110.0)
        await engine.close_position(symbol, strategy_name="MeanReversionStrategy")

        trades = engine.get_trade_history()
        assert len(trades) == 1
        assert trades[0].strategy_name == "MeanReversionStrategy"
        assert trades[0].pnl > 0  # price went up

    @pytest.mark.asyncio
    async def test_different_strategies_get_different_trades(self, engine, exchange):
        """Different strategies should produce separate trade records."""
        symbol = "BTC-USDT"

        # Strategy 1 opens a long
        await engine.open_position(symbol, "long", 0.5, strategy_name="GridStrategy")
        exchange.set_price(symbol, 105.0)
        await engine.close_position(symbol, strategy_name="GridStrategy")

        # Strategy 2 opens another long
        await engine.open_position(symbol, "long", 0.5, strategy_name="RSI+BollingerStrategy")
        exchange.set_price(symbol, 110.0)
        await engine.close_position(symbol, strategy_name="RSI+BollingerStrategy")

        trades = engine.get_trade_history()
        assert len(trades) == 2

        strategies = {t.strategy_name for t in trades}
        assert strategies == {"GridStrategy", "RSI+BollingerStrategy"}

    @pytest.mark.asyncio
    async def test_strategy_falls_back_to_stored_name(self, engine, exchange):
        """If no strategy passed to close, falls back to stored name."""
        symbol = "BTC-USDT"

        await engine.open_position(symbol, "long", 1.0, strategy_name="MomentumStrategy")
        exchange.set_price(symbol, 120.0)
        # Don't pass strategy_name to close_position
        await engine.close_position(symbol)

        trades = engine.get_trade_history()
        assert trades[0].strategy_name == "MomentumStrategy"

    @pytest.mark.asyncio
    async def test_empty_strategy_name_when_not_provided(self, engine, exchange):
        """Trades without strategy attribution get empty string."""
        symbol = "ETH-USDT"

        # Open without strategy
        await engine.open_position(symbol, "long", 2.0, strategy_name="")
        exchange.set_price(symbol, 200.0)
        await engine.close_position(symbol)

        trades = engine.get_trade_history()
        assert trades[0].strategy_name == ""


class TestPerformanceLogger:
    """Test per-strategy performance aggregation."""

    @pytest.fixture
    def logger(self, tmp_path):
        return PerformanceLogger(log_dir=tmp_path / "perf")

    def test_strategy_comparison_ranking(self, logger, tmp_path):
        """Strategy comparison should rank by total P&L."""
        now = datetime.utcnow()

        # Log trades for two strategies
        for i, strategy in enumerate(["GridStrategy", "RSI+Bollinger"]):
            for j in range(3):
                trade = SimulatedTrade(
                    trade_id=f"trade_{i}_{j}",
                    symbol="BTC-USDT",
                    side="sell",
                    quantity=1.0,
                    entry_price=100.0,
                    exit_price=105.0 + i * 5,  # RSI better than Grid
                    pnl=5.0 + i * 5,
                    fee=0.1,
                    opened_at=now - timedelta(hours=j + 1),
                    closed_at=now - timedelta(hours=j),
                    strategy_name=strategy,
                )
                logger.log_trade_summary(trade)

        comparison = logger.get_strategy_comparison(days=1)

        assert "ranked_strategies" in comparison
        ranked = comparison["ranked_strategies"]
        assert len(ranked) == 2
        # RSI+Bollinger should be ranked #1 (higher P&L)
        assert ranked[0]["strategy"] == "RSI+Bollinger"
        assert ranked[0]["rank"] == 1
        assert ranked[1]["strategy"] == "GridStrategy"
        assert ranked[1]["rank"] == 2

    def test_strategy_performance_includes_sharpe(self, logger, tmp_path):
        """Per-strategy stats include Sharpe ratio."""
        now = datetime.utcnow()

        for i in range(5):
            trade = SimulatedTrade(
                trade_id=f"trade_{i}",
                symbol="BTC-USDT",
                side="sell",
                quantity=1.0,
                entry_price=100.0,
                exit_price=102.0,
                pnl=2.0,
                fee=0.1,
                opened_at=now - timedelta(hours=i + 1),
                closed_at=now - timedelta(hours=i),
                strategy_name="MomentumStrategy",
            )
            logger.log_trade_summary(trade)

        stats = logger.get_strategy_performance(days=1)

        assert "MomentumStrategy" in stats
        s = stats["MomentumStrategy"]
        assert s["num_trades"] == 5
        assert s["win_rate"] == 1.0  # all winners
        assert "sharpe_ratio" in s
        assert "std_dev" in s

    def test_unknown_strategy_for_legacy_trades(self, logger, tmp_path):
        """Trades logged before strategy_name field get 'unknown' attribution."""
        now = datetime.utcnow()

        # Legacy trade (no strategy_name field)
        trade = SimulatedTrade(
            trade_id="legacy_trade",
            symbol="BTC-USDT",
            side="sell",
            quantity=1.0,
            entry_price=100.0,
            exit_price=110.0,
            pnl=10.0,
            fee=0.1,
            opened_at=now - timedelta(hours=1),
            closed_at=now,
            strategy_name="",  # empty default
        )
        logger.log_trade_summary(trade)

        stats = logger.get_strategy_performance(days=1)
        # Empty string strategy becomes "unknown" in aggregation
        assert "unknown" in stats or "" in stats