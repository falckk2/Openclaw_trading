"""Tests for trading module."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.trading.engine import TradingEngine
from src.trading.position import Position
from src.trading.order_manager import OrderManager, TrackedOrder
from src.config.dataclasses import RiskConfig
from src.exchange.base import ExchangeClient, OrderResponse


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