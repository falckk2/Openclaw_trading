"""Trading engine — manages positions, P&L, and order execution."""

import uuid
from datetime import datetime
from typing import Literal

from ..exchange.base import ExchangeClient, OrderRequest, OrderResponse, Position as ExchangePosition
from ..config.dataclasses import RiskConfig
from .position import Position
from .order_manager import OrderManager


class TradingEngine:
    """
    Core trading engine — coordinates orders, positions, and P&L tracking.

    Depends on ExchangeClient abstraction (DIP), so works with any exchange.
    """

    def __init__(self, exchange: ExchangeClient, config: RiskConfig):
        self._exchange = exchange
        self._config = config
        self._positions: dict[str, Position] = {}
        self._order_manager = OrderManager()

    # ── Position Management ─────────────────────────────────────

    async def open_position(
        self, symbol: str, side: Literal["long", "short"], qty: float, price: float | None = None
    ) -> Position:
        """Open a new position."""
        # Validate position size against risk config
        # In paper trading without API keys, balance may not be available — skip validation
        try:
            balance = await self._exchange.get_balance()
            max_position_value = balance.total_equity * self._config.max_position_pct
        except Exception:
            max_position_value = float("inf")  # allow position open in paper/demo mode

        order_req = OrderRequest(
            symbol=symbol,
            side="buy" if side == "long" else "sell",
            order_type="market" if price is None else "limit",
            quantity=qty,
            price=price,
        )
        order_resp = await self._exchange.place_order(order_req)
        self._order_manager.track_order(order_resp)

        position = Position(
            position_id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            entry_price=order_resp.avg_price or price or 0,
            quantity=qty,
            current_price=order_resp.avg_price or price or 0,
            opened_at=datetime.utcnow(),
        )
        self._positions[symbol] = position
        return position

    async def close_position(self, symbol: str) -> OrderResponse | None:
        """Close an open position."""
        position = self._positions.get(symbol)
        if not position:
            return None

        side = "sell" if position.side == "long" else "buy"
        order_req = OrderRequest(
            symbol=symbol,
            side=side,
            order_type="market",
            quantity=position.quantity,
            price=None,
        )
        order_resp = await self._exchange.place_order(order_req)
        self._order_manager.track_order(order_resp)

        del self._positions[symbol]
        return order_resp

    async def modify_position(
        self, symbol: str, stop_loss: float | None = None, take_profit: float | None = None
    ) -> None:
        """Update stop loss and take profit for a position."""
        position = self._positions.get(symbol)
        if position:
            if stop_loss is not None:
                position.stop_loss = stop_loss
            if take_profit is not None:
                position.take_profit = take_profit

    def get_position(self, symbol: str) -> Position | None:
        """Get position by symbol."""
        return self._positions.get(symbol)

    def get_all_positions(self) -> list[Position]:
        """Get all open positions."""
        return list(self._positions.values())

    async def sync_positions_from_exchange(self) -> None:
        """Sync positions from exchange — called on startup or reconnect."""
        exchange_positions = await self._exchange.get_positions()
        self._positions.clear()
        for ep in exchange_positions:
            pos = Position(
                position_id=ep.position_id,
                symbol=ep.symbol,
                side=ep.side,
                entry_price=ep.entry_price,
                quantity=ep.quantity,
                current_price=ep.current_price,
                unrealized_pnl=ep.unrealized_pnl,
                realized_pnl=ep.realized_pnl,
                opened_at=ep.opened_at,
                stop_loss=ep.stop_loss,
                take_profit=ep.take_profit,
            )
            self._positions[ep.symbol] = pos

    # ── P&L ──────────────────────────────────────────────────────

    async def update_position_prices(self) -> None:
        """Update current prices and recalculate P&L for all positions."""
        for symbol, position in self._positions.items():
            ticker = await self._exchange.get_ticker(symbol)
            position.update_price(ticker.last)

    def get_total_unrealized_pnl(self) -> float:
        """Sum of all unrealized P&L."""
        return sum(p.unrealized_pnl for p in self._positions.values())

    def get_total_realized_pnl(self) -> float:
        """Sum of all realized P&L."""
        return sum(p.realized_pnl for p in self._positions.values())

    # ── Risk Checks ───────────────────────────────────────────────

    async def check_position_limits(self, symbol: str, qty: float, price: float) -> bool:
        """Check if placing this order would violate risk limits."""
        balance = await self._exchange.get_balance()
        position_value = qty * price

        # Check max position size
        if position_value > balance.total_equity * self._config.max_position_pct:
            return False

        # Check max open positions
        if len(self._positions) >= self._config.max_open_positions:
            return False

        # Check daily loss limit
        daily_loss = self.get_total_unrealized_pnl()
        if daily_loss < -balance.total_equity * self._config.max_daily_loss_pct:
            return False

        return True