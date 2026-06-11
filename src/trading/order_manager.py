"""Order manager — tracks open orders and handles cancellation."""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Literal

from ..exchange.base import OrderResponse


@dataclass
class TrackedOrder:
    """An order being tracked by the order manager."""
    order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"]
    quantity: float
    price: float | None
    filled_qty: float
    status: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class OrderManager:
    """Manages open orders and tracks fill status."""

    def __init__(self):
        self._orders: dict[str, TrackedOrder] = {}
        self._symbol_orders: dict[str, list[str]] = defaultdict(list)

    def track_order(self, order: OrderResponse) -> TrackedOrder:
        """Track a newly placed order."""
        tracked = TrackedOrder(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.avg_price if order.avg_price else None,
            filled_qty=order.filled_qty,
            status=order.status,
        )
        self._orders[order.order_id] = tracked
        self._symbol_orders[order.symbol].append(order.order_id)
        return tracked

    def update_order(self, order: OrderResponse) -> TrackedOrder | None:
        """Update a tracked order with latest data."""
        tracked = self._orders.get(order.order_id)
        if tracked:
            tracked.filled_qty = order.filled_qty
            tracked.status = order.status
        return tracked

    def get_order(self, order_id: str) -> TrackedOrder | None:
        """Get a tracked order by ID."""
        return self._orders.get(order_id)

    def get_open_orders(self, symbol: str | None = None) -> list[TrackedOrder]:
        """Get all open (non-filled/cancelled) orders, optionally filtered by symbol."""
        if symbol:
            order_ids = self._symbol_orders.get(symbol, [])
            return [
                self._orders[oid]
                for oid in order_ids
                if oid in self._orders
                and self._orders[oid].status not in ("filled", "cancelled")
            ]
        return [o for o in self._orders.values() if o.status not in ("filled", "cancelled")]

    def remove_order(self, order_id: str) -> None:
        """Remove a completed order from tracking."""
        tracked = self._orders.pop(order_id, None)
        if tracked:
            self._symbol_orders[tracked.symbol].remove(order_id)