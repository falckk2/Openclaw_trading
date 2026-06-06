"""Performance logger — logs daily/weekly performance summaries."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..paper_trading.order_tracker import SimulatedTrade


class PerformanceLogger:
    """Logs performance metrics and summaries."""

    def __init__(self, log_dir: Path | str = "logs/performance"):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def _log_json(self, filename: str, data: dict) -> None:
        path = self._log_dir / filename
        with open(path, "a") as f:
            f.write(json.dumps(data) + "\n")

    def log_daily_summary(
        self,
        date: str,
        total_trades: int,
        winning_trades: int,
        total_pnl: float,
        unrealized_pnl: float,
        equity: float,
    ) -> None:
        """Log end-of-day performance summary."""
        self._log_json("daily_summaries.jsonl", {
            "type": "daily_summary",
            "date": date,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "win_rate": winning_trades / total_trades if total_trades > 0 else 0,
            "total_pnl": total_pnl,
            "unrealized_pnl": unrealized_pnl,
            "equity": equity,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def log_trade_summary(self, trade: SimulatedTrade) -> None:
        """Log a completed trade."""
        self._log_json("trade_summaries.jsonl", {
            "type": "trade",
            "trade_id": trade.trade_id,
            "symbol": trade.symbol,
            "side": trade.side,
            "quantity": trade.quantity,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "pnl": trade.pnl,
            "fee": trade.fee,
            "opened_at": trade.opened_at.isoformat(),
            "closed_at": trade.closed_at.isoformat(),
            "duration_seconds": (trade.closed_at - trade.opened_at).total_seconds(),
            "timestamp": datetime.utcnow().isoformat(),
        })

    def get_performance_stats(self, days: int = 7) -> dict:
        """Calculate performance stats over last N days from logs."""
        path = self._log_dir / "daily_summaries.jsonl"
        if not path.exists():
            return {}

        summaries = []
        cutoff = datetime.utcnow() - timedelta(days=days)
        with open(path) as f:
            for line in f:
                entry = json.loads(line)
                if datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")) >= cutoff:
                    summaries.append(entry)

        if not summaries:
            return {}

        total_pnl = sum(s["total_pnl"] for s in summaries)
        total_trades = sum(s["total_trades"] for s in summaries)
        winning = sum(s["winning_trades"] for s in summaries)

        return {
            "period_days": days,
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "winning_trades": winning,
            "win_rate": winning / total_trades if total_trades > 0 else 0,
            "avg_pnl_per_day": total_pnl / days,
        }