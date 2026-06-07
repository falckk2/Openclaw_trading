"""Tests for trading module."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.trading.engine import TradingEngine
from src.trading.position import Position
from src.trading.order_manager import OrderManager, TrackedOrder
from src.config.dataclasses import RiskConfig
from src.exchange.base import ExchangeClient, OrderResponse
from src.data.dataclasses import Candle
from datetime import datetime, timedelta


class TestPosition:
    """Tests for Position dataclass."""

    def test_update_price_long(self):
        """Long position P&L updates correctly with price change."""
        pos = Position(
            position_id="p1",
            symbol="BTCUSDT",
            side="long",
            entry_price=50000.0,
            quantity=0.01,
            current_price=50000.0,
        )
        pos.update_price(51000.0)
        assert pos.unrealized_pnl == (51000 - 50000) * 0.01  # 10

    def test_update_price_short(self):
        """Short position P&L updates correctly with price change."""
        pos = Position(
            position_id="p1",
            symbol="BTCUSDT",
            side="short",
            entry_price=50000.0,
            quantity=0.01,
            current_price=50000.0,
        )
        pos.update_price(49000.0)
        assert pos.unrealized_pnl == (50000 - 49000) * 0.01  # 10

    def test_get_pnl_pct(self):
        """P&L percentage calculated correctly."""
        pos = Position(
            position_id="p1",
            symbol="BTCUSDT",
            side="long",
            entry_price=50000.0,
            quantity=0.01,
            current_price=51000.0,
        )
        pct = pos.get_pnl_pct()
        assert abs(pct - 2.0) < 0.01  # 2%


class TestOrderManager:
    """Tests for OrderManager."""

    def test_track_order(self):
        """Orders are tracked correctly."""
        manager = OrderManager()
        order = OrderResponse(
            order_id="ord_123",
            symbol="BTCUSDT",
            status="filled",
            side="buy",
            order_type="market",
            quantity=0.01,
            filled_qty=0.01,
            avg_price=50000.0,
        )
        tracked = manager.track_order(order)
        assert tracked.order_id == "ord_123"
        assert tracked.symbol == "BTCUSDT"

    def test_get_open_orders(self):
        """Only open orders returned."""
        manager = OrderManager()
        order = OrderResponse(
            order_id="ord_456",
            symbol="BTCUSDT",
            status="filled",
            side="buy",
            order_type="market",
            quantity=0.01,
            filled_qty=0.01,
            avg_price=50000.0,
        )
        manager.track_order(order)
        open_orders = manager.get_open_orders("BTCUSDT")
        # Filled orders should not appear in open orders
        assert all(o.status != "filled" for o in open_orders)


class TestPositionATR:
    """Tests for ATR-based dynamic stop loss."""

    def test_calculate_atr_basic(self):
        """ATR is positive and reasonable."""
        pos = Position(
            position_id="p1",
            symbol="BTCUSDT",
            side="long",
            entry_price=50000.0,
            quantity=0.01,
            current_price=50000.0,
            atr_period=14,
        )

        # Create realistic candle data
        candles = [
            Candle(
                timestamp=datetime.utcnow() - timedelta(hours=14 - i),
                open=50000 + i * 20,
                high=50100 + i * 20,
                low=49900 + i * 20,
                close=50000 + i * 20,
                volume=1000,
            )
            for i in range(15)
        ]

        atr = pos.calculate_atr(candles)
        assert atr > 0
        # ATR should be less than price (typical ATR for BTC is 100s-1000s)
        assert atr < 50000

    def test_calculate_atr_insufficient_data(self):
        """ATR returns 0 when not enough data."""
        pos = Position(
            position_id="p1",
            symbol="BTCUSDT",
            side="long",
            entry_price=50000.0,
            quantity=0.01,
            current_price=50000.0,
            atr_period=14,
        )

        candles = [
            Candle(
                timestamp=datetime.utcnow() - timedelta(hours=i),
                open=50000,
                high=50100,
                low=49900,
                close=50000,
                volume=1000,
            )
            for i in range(5)
        ]

        atr = pos.calculate_atr(candles)
        assert atr >= 0  # Should not crash, may return 0

    def test_update_stop_loss_atr_long(self):
        """ATR stop loss set correctly for long position."""
        pos = Position(
            position_id="p1",
            symbol="BTCUSDT",
            side="long",
            entry_price=50000.0,
            quantity=0.01,
            current_price=50000.0,
            atr_multiplier=2.0,
            atr_period=14,
        )

        candles = [
            Candle(
                timestamp=datetime.utcnow() - timedelta(hours=14 - i),
                open=50000 + i * 20,
                high=50150 + i * 20,
                low=49850 + i * 20,
                close=50000 + i * 20,
                volume=1000,
            )
            for i in range(15)
        ]

        stop = pos.update_stop_loss_atr(candles)
        assert stop is not None
        # For long: stop should be below current price
        assert stop < 50000.0
        # Stop should be within reasonable range (not too far)
        assert stop > 49000  # ATR-based stop shouldn't be 1000s away

    def test_update_stop_loss_atr_short(self):
        """ATR stop loss set correctly for short position."""
        pos = Position(
            position_id="p1",
            symbol="BTCUSDT",
            side="short",
            entry_price=50000.0,
            quantity=0.01,
            current_price=50000.0,
            atr_multiplier=2.0,
            atr_period=14,
        )

        candles = [
            Candle(
                timestamp=datetime.utcnow() - timedelta(hours=14 - i),
                open=50000 + i * 20,
                high=50150 + i * 20,
                low=49850 + i * 20,
                close=50000 + i * 20,
                volume=1000,
            )
            for i in range(15)
        ]

        stop = pos.update_stop_loss_atr(candles)
        assert stop is not None
        # For short: stop should be above current price
        assert stop > 50000.0

    def test_check_stop_loss_triggered_long(self):
        """Stop loss triggers correctly for long position."""
        pos = Position(
            position_id="p1",
            symbol="BTCUSDT",
            side="long",
            entry_price=50000.0,
            quantity=0.01,
            current_price=50000.0,
            stop_loss=49500.0,
        )

        # Price drops to stop loss
        assert pos.check_stop_loss_triggered(49500.0)
        # Price above stop
        assert not pos.check_stop_loss_triggered(50000.0)

    def test_check_stop_loss_triggered_short(self):
        """Stop loss triggers correctly for short position."""
        pos = Position(
            position_id="p1",
            symbol="BTCUSDT",
            side="short",
            entry_price=50000.0,
            quantity=0.01,
            current_price=50000.0,
            stop_loss=50500.0,
        )

        # Price rises to stop loss
        assert pos.check_stop_loss_triggered(50500.0)
        # Price below stop
        assert not pos.check_stop_loss_triggered(50000.0)

    def test_trailing_stop_long(self):
        """Trailing stop only raises for long position."""
        pos = Position(
            position_id="p1",
            symbol="BTCUSDT",
            side="long",
            entry_price=50000.0,
            quantity=0.01,
            current_price=50000.0,
            atr_multiplier=2.0,
            atr_period=14,
            stop_loss=49000.0,  # initial stop
        )

        candles = [
            Candle(
                timestamp=datetime.utcnow() - timedelta(hours=14 - i),
                open=50000 + i * 20,
                high=50150 + i * 20,
                low=49850 + i * 20,
                close=50000 + i * 20,
                volume=1000,
            )
            for i in range(15)
        ]

        # Price moves up to 51000 - trailing stop should raise
        pos.current_price = 51000.0
        new_stop = pos.update_stop_loss_atr(candles, trailing=True)
        assert new_stop is not None
        # Trailing stop should be higher than original
        assert new_stop >= 49000.0

    def test_take_profit_atr(self):
        """Take profit set based on ATR."""
        pos = Position(
            position_id="p1",
            symbol="BTCUSDT",
            side="long",
            entry_price=50000.0,
            quantity=0.01,
            current_price=50000.0,
            atr_period=14,
        )

        candles = [
            Candle(
                timestamp=datetime.utcnow() - timedelta(hours=14 - i),
                open=50000 + i * 20,
                high=50150 + i * 20,
                low=49850 + i * 20,
                close=50000 + i * 20,
                volume=1000,
            )
            for i in range(15)
        ]

        tp = pos.set_take_profit_atr(candles, reward_multiplier=3.0)
        assert tp is not None
        # TP for long should be above entry
        assert tp > 50000.0

    def test_check_take_profit_triggered(self):
        """Take profit triggers correctly."""
        pos = Position(
            position_id="p1",
            symbol="BTCUSDT",
            side="long",
            entry_price=50000.0,
            quantity=0.01,
            current_price=50000.0,
            take_profit=51000.0,
        )

        # Price reaches TP
        assert pos.check_take_profit_triggered(51000.0)
        # Price below TP
        assert not pos.check_take_profit_triggered(50500.0)

    def test_get_risk_reward_ratio(self):
        """Risk/reward ratio calculated correctly."""
        pos = Position(
            position_id="p1",
            symbol="BTCUSDT",
            side="long",
            entry_price=50000.0,
            quantity=0.01,
            current_price=50000.0,
            stop_loss=49500.0,   # risk: 500
            take_profit=51500.0,  # reward: 1500
        )

        rr = pos.get_risk_reward_ratio()
        assert rr is not None
        assert rr == 3.0  # 1500 / 500 = 3

    def test_get_stop_loss_distance_pct(self):
        """Stop loss distance as percentage calculated."""
        pos = Position(
            position_id="p1",
            symbol="BTCUSDT",
            side="long",
            entry_price=50000.0,
            quantity=0.01,
            current_price=50000.0,
            stop_loss=49500.0,
        )

        dist = pos.get_stop_loss_distance_pct()
        assert abs(dist - 1.0) < 0.01  # 1% distance