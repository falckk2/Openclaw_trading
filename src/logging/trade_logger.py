"""Trade logger — logs every trade, signal, and P&L update."""

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from ..strategies.signal import Signal
from ..exchange.base import OrderResponse, Position


class TradeLogger:
    """Logs all trading events to structured JSON files."""

    def __init__(self, log_dir: Path | str = "logs/trades"):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def _log_event(self, filename: str, event: dict) -> None:
        """Append a JSON event to a log file."""
        path = self._log_dir / filename
        with open(path, "a") as f:
            f.write(json.dumps(event) + "\n")

    def log_signal(self, signal: Signal) -> None:
        """Log a trading signal."""
        self._log_event("signals.jsonl", {
            "type": "signal",
            "timestamp": datetime.now(UTC).isoformat(),
            "signal_id": signal.signal_id,
            "strategy": signal.strategy_name,
            "symbol": signal.symbol,
            "action": signal.action,
            "confidence": signal.confidence,
            "entry_price": signal.entry_price,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "metadata": signal.metadata,
        })

    def log_order(self, order: OrderResponse) -> None:
        """Log an order response."""
        self._log_event("orders.jsonl", {
            "type": "order",
            "timestamp": datetime.now(UTC).isoformat(),
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side,
            "status": order.status,
            "filled_qty": order.filled_qty,
            "avg_price": order.avg_price,
            "fee": order.fee,
        })

    def log_position(self, position: Position | Any) -> None:
        """Log position state."""
        self._log_event("positions.jsonl", {
            "type": "position",
            "timestamp": datetime.now(UTC).isoformat(),
            "symbol": position.symbol,
            "side": position.side,
            "entry_price": position.entry_price,
            "quantity": position.quantity,
            "current_price": position.current_price,
            "unrealized_pnl": position.unrealized_pnl,
        })

    def log_pnl(self, realized: float, unrealized: float, total_equity: float) -> None:
        """Log P&L snapshot."""
        self._log_event("pnl.jsonl", {
            "type": "pnl",
            "timestamp": datetime.now(UTC).isoformat(),
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "total_equity": total_equity,
        })