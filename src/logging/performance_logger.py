"""Performance logger — logs daily/weekly performance summaries."""

import json
from datetime import datetime, timedelta, UTC
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
        strategy_pnl: dict[str, float] | None = None,
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
            "strategy_pnl": strategy_pnl or {},
            "timestamp": datetime.now(UTC).isoformat(),
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
            "strategy_name": trade.strategy_name,
            "opened_at": trade.opened_at.isoformat(),
            "closed_at": trade.closed_at.isoformat(),
            "duration_seconds": (trade.closed_at - trade.opened_at).total_seconds(),
            "timestamp": datetime.now(UTC).isoformat(),
        })

    def get_performance_stats(self, days: int = 7) -> dict:
        """Calculate performance stats over last N days from logs."""
        path = self._log_dir / "daily_summaries.jsonl"
        if not path.exists():
            return {}

        summaries = []
        cutoff = datetime.now(UTC) - timedelta(days=days)
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

    def get_strategy_performance(self, days: int = 7) -> dict[str, dict]:
        """Calculate per-strategy performance stats over last N days."""
        path = self._log_dir / "trade_summaries.jsonl"
        if not path.exists():
            return {}

        cutoff = datetime.now(UTC) - timedelta(days=days)
        by_strategy: dict[str, list[dict]] = {}

        with open(path) as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("type") != "trade":
                    continue
                ts = datetime.fromisoformat(entry["closed_at"].replace("Z", "+00:00"))
                if ts >= cutoff:
                    strategy = entry.get("strategy_name", "unknown") or "unknown"
                    by_strategy.setdefault(strategy, []).append(entry)

        result = {}
        for strategy, trades in by_strategy.items():
            pnls = [t["pnl"] for t in trades]
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p <= 0]
            durations = [t["duration_seconds"] for t in trades]

            total_pnl = sum(pnls)
            avg_pnl = total_pnl / len(pnls) if pnls else 0
            std_pnl = (sum((p - avg_pnl) ** 2 for p in pnls) / len(pnls)) ** 0.5 if len(pnls) > 1 else 0

            result[strategy] = {
                "total_pnl": total_pnl,
                "num_trades": len(trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": len(wins) / len(trades) if trades else 0,
                "avg_pnl_per_trade": avg_pnl,
                "best_trade": max(pnls) if pnls else 0,
                "worst_trade": min(pnls) if pnls else 0,
                "std_dev": std_pnl,
                "sharpe_ratio": (avg_pnl / std_pnl) if std_pnl > 0 else 0,
                "avg_duration_seconds": sum(durations) / len(durations) if durations else 0,
            }

        return result

    def get_strategy_comparison(self, days: int = 7) -> dict:
        """Compare all strategies side-by-side."""
        by_strategy = self.get_strategy_performance(days)
        if not by_strategy:
            return {"error": "No trade data found", "days": days}

        sorted_strategies = sorted(
            by_strategy.items(), key=lambda x: x[1]["total_pnl"], reverse=True
        )

        comparison = {"period_days": days, "ranked_strategies": []}
        for rank, (strategy, stats) in enumerate(sorted_strategies, 1):
            comparison["ranked_strategies"].append({
                "rank": rank,
                "strategy": strategy,
                "total_pnl": round(stats["total_pnl"], 4),
                "num_trades": stats["num_trades"],
                "win_rate": f"{stats['win_rate']:.1%}",
                "avg_pnl": round(stats["avg_pnl_per_trade"], 4),
                "sharpe_ratio": round(stats["sharpe_ratio"], 2),
                "best_trade": round(stats["best_trade"], 4),
                "worst_trade": round(stats["worst_trade"], 4),
                "avg_duration": f"{stats['avg_duration_seconds']:.0f}s",
            })

        return comparison