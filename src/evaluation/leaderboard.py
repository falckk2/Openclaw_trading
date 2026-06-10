"""
Agent/Strategy Leaderboard — ranks trading agents by performance.

Provides:
- Multi-metric ranking (P&L, Sharpe, win rate, drawdown)
- Historical tracking of rankings over time
- Best-in-class identification
- Head-to-head comparison

The leaderboard tracks:
- Strategies (rule-based and ML)
- Models (trained agents)
- Combined performance across time periods
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any

from ..logging.performance_logger import PerformanceLogger


@dataclass
class AgentRanking:
    """Ranking information for a single agent."""
    agent_id: str  # e.g. "GridStrategy:v1", "DNNModel:v2.3"
    agent_name: str  # e.g. "GridStrategy"
    agent_type: str  # e.g. "strategy", "model"
    rank: int
    total_pnl: float
    win_rate: float
    sharpe_ratio: float
    max_drawdown_pct: float
    num_trades: int
    avg_pnl_per_trade: float
    period_days: int
    evaluated_at: str
    trend: str  # "up", "down", "stable" compared to previous period


@dataclass
class LeaderboardEntry:
    """Full leaderboard entry with all metrics."""
    agent_id: str
    agent_name: str
    agent_type: str
    metrics: dict[str, Any]
    history: list[dict]  # historical rankings
    first_appeared: str
    last_evaluated: str


class Leaderboard:
    """
    Tracks and ranks trading agents (strategies + models).

    SOLID:
    - SRP: only handles ranking and leaderboard logic
    - OCP: add new ranking criteria without modifying core
    - DIP: depends on PerformanceLogger abstraction

    Rankings are computed from:
    - Trade summaries (via PerformanceLogger)
    - Checkpoint metadata (via CheckpointManager)
    - Evaluation results (via ModelEvaluator)
    """

    def __init__(
        self,
        log_dir: Path | str = "logs/leaderboard",
        performance_logger: PerformanceLogger | None = None,
    ):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._perf_logger = performance_logger or PerformanceLogger(log_dir=str(Path(log_dir).parent / "performance"))
        self._rankings_path = self._log_dir / "rankings.jsonl"
        self._leaderboard_path = self._log_dir / "leaderboard.json"

    def update_rankings(
        self,
        agents: list[dict[str, Any]],
        period_days: int = 7,
    ) -> list[AgentRanking]:
        """
        Update rankings for all agents based on recent performance.

        Args:
            agents: list of agent dicts with keys: agent_id, agent_name, agent_type
            period_days: time period to evaluate (default 7 days)

        Returns:
            List of AgentRanking sorted by rank
        """
        # Get performance data
        strategy_stats = self._perf_logger.get_strategy_performance(days=period_days)

        rankings = []
        for agent in agents:
            agent_id = agent["agent_id"]
            agent_name = agent.get("agent_name", agent_id)
            agent_type = agent.get("agent_type", "strategy")

            # Get stats for this agent
            stats = strategy_stats.get(agent_name, {})

            if stats:
                # Calculate trend
                previous = self._get_previous_rank(agent_id)
                trend = self._calculate_trend(stats, previous)

                ranking = AgentRanking(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    agent_type=agent_type,
                    rank=0,  # set after sorting
                    total_pnl=stats.get("total_pnl", 0.0),
                    win_rate=stats.get("win_rate", 0.0),
                    sharpe_ratio=stats.get("sharpe_ratio", 0.0),
                    max_drawdown_pct=stats.get("max_drawdown_pct", 0.0),
                    num_trades=stats.get("num_trades", 0),
                    avg_pnl_per_trade=stats.get("avg_pnl_per_trade", 0.0),
                    period_days=period_days,
                    evaluated_at=datetime.now(UTC).isoformat(),
                    trend=trend,
                )
                rankings.append(ranking)

        # Sort by composite score: P&L weighted by Sharpe
        rankings.sort(key=lambda r: self._composite_score(r), reverse=True)

        # Assign ranks
        for i, ranking in enumerate(rankings, 1):
            ranking.rank = i

        # Save rankings
        self._save_rankings(rankings)
        self._save_leaderboard_snapshot(rankings)

        return rankings

    def _composite_score(self, ranking: AgentRanking) -> float:
        """
        Calculate composite score for ranking.
        P&L weighted by Sharpe ratio (higher is better).
        """
        pnl_score = ranking.total_pnl
        sharpe_bonus = ranking.sharpe_ratio * abs(ranking.total_pnl) * 0.1
        return pnl_score + sharpe_bonus

    def _calculate_trend(self, current_stats: dict, previous_rank: int | None) -> str:
        """Calculate trend compared to previous ranking."""
        if previous_rank is None:
            return "stable"

        current_pnl = current_stats.get("total_pnl", 0)
        if current_pnl > 0.01:
            return "up"
        elif current_pnl < -0.01:
            return "down"
        return "stable"

    def _get_previous_rank(self, agent_id: str) -> int | None:
        """Get previous rank for an agent from last ranking."""
        if not self._rankings_path.exists():
            return None

        try:
            with open(self._rankings_path) as f:
                lines = f.readlines()
                if not lines:
                    return None

                last_line = json.loads(lines[-1])
                for entry in last_line.get("rankings", []):
                    if entry["agent_id"] == agent_id:
                        return entry.get("rank")
        except (json.JSONDecodeError, IndexError):
            pass

        return None

    def _save_rankings(self, rankings: list[AgentRanking]) -> None:
        """Append current rankings to history."""
        with open(self._rankings_path, "a") as f:
            f.write(json.dumps({
                "timestamp": datetime.now(UTC).isoformat(),
                "rankings": [r.__dict__ for r in rankings],
            }) + "\n")

    def _save_leaderboard_snapshot(self, rankings: list[AgentRanking]) -> None:
        """Save current leaderboard as JSON."""
        data = {
            "updated_at": datetime.now(UTC).isoformat(),
            "rankings": [r.__dict__ for r in rankings],
        }
        with open(self._leaderboard_path, "w") as f:
            json.dump(data, f, indent=2)

    def get_leaderboard(self, limit: int = 10) -> list[AgentRanking]:
        """Get current leaderboard (top N)."""
        path = self._leaderboard_path
        if not path.exists():
            return []

        with open(path) as f:
            data = json.load(f)

        rankings = [AgentRanking(**r) for r in data.get("rankings", [])]
        return rankings[:limit]

    def get_agent_history(self, agent_id: str) -> list[dict]:
        """Get ranking history for a specific agent."""
        history = []

        if not self._rankings_path.exists():
            return history

        with open(self._rankings_path) as f:
            for line in f:
                entry = json.loads(line)
                for r in entry.get("rankings", []):
                    if r["agent_id"] == agent_id:
                        history.append({
                            "timestamp": entry["timestamp"],
                            "rank": r["rank"],
                            "total_pnl": r["total_pnl"],
                            "sharpe_ratio": r["sharpe_ratio"],
                        })

        return history

    def get_best_agent(
        self,
        agent_type: str | None = None,
        metric: str = "total_pnl",
    ) -> AgentRanking | None:
        """
        Get the best-performing agent overall or by type.

        Args:
            agent_type: filter by type ("strategy" or "model"), None for all
            metric: metric to rank by ("total_pnl", "sharpe_ratio", "win_rate")

        Returns:
            Best AgentRanking or None
        """
        leaderboard = self.get_leaderboard(limit=100)
        if agent_type:
            leaderboard = [r for r in leaderboard if r.agent_type == agent_type]

        if not leaderboard:
            return None

        return max(leaderboard, key=lambda r: getattr(r, metric, 0))

    def compare_agents(
        self,
        agent_id_1: str,
        agent_id_2: str,
    ) -> dict[str, Any]:
        """
        Head-to-head comparison of two agents.

        Returns comparison metrics and historical performance.
        """
        history1 = self.get_agent_history(agent_id_1)
        history2 = self.get_agent_history(agent_id_2)

        def summarize(history):
            if not history:
                return {"appearances": 0, "avg_rank": None, "total_pnl": None}
            ranks = [h["rank"] for h in history if h.get("rank")]
            pnls = [h["total_pnl"] for h in history if h.get("total_pnl") is not None]
            return {
                "appearances": len(history),
                "avg_rank": sum(ranks) / len(ranks) if ranks else None,
                "best_rank": min(ranks) if ranks else None,
                "total_pnl": sum(pnls) if pnls else None,
            }

        return {
            "agent_1": agent_id_1,
            "agent_2": agent_id_2,
            "summary_1": summarize(history1),
            "summary_2": summarize(history2),
            "history_1": history1[-10:],  # last 10 appearances
            "history_2": history2[-10:],
        }

    def generate_report(self, period_days: int = 30) -> dict[str, Any]:
        """
        Generate a comprehensive leaderboard report.

        Args:
            period_days: period to cover in report

        Returns:
            Report dict with rankings, insights, and recommendations
        """
        leaderboard = self.get_leaderboard(limit=20)
        if not leaderboard:
            return {"error": "No data available"}

        # Calculate insights
        top_agents = leaderboard[:3]
        best_sharpe = max(leaderboard, key=lambda r: r.sharpe_ratio)
        most_trades = max(leaderboard, key=lambda r: r.num_trades)
        best_win_rate = max(leaderboard, key=lambda r: r.win_rate)

        # Trend analysis
        improving = [r for r in leaderboard if r.trend == "up"]
        declining = [r for r in leaderboard if r.trend == "down"]

        return {
            "report_date": datetime.now(UTC).isoformat(),
            "period_days": period_days,
            "total_agents": len(leaderboard),
            "top_3": [
                {"rank": r.rank, "agent": r.agent_name, "pnl": round(r.total_pnl, 4)}
                for r in top_agents
            ],
            "highlights": {
                "best_by_pnl": {"agent": leaderboard[0].agent_name, "pnl": round(leaderboard[0].total_pnl, 4)},
                "best_by_sharpe": {"agent": best_sharpe.agent_name, "sharpe": round(best_sharpe.sharpe_ratio, 2)},
                "most_active": {"agent": most_trades.agent_name, "trades": most_trades.num_trades},
                "best_win_rate": {"agent": best_win_rate.agent_name, "win_rate": f"{best_win_rate.win_rate:.1%}"},
            },
            "trends": {
                "improving": [r.agent_name for r in improving],
                "declining": [r.agent_name for r in declining],
            },
            "rankings": [r.__dict__ for r in leaderboard],
        }

    def save_report(self, report: dict[str, Any], name: str = "weekly") -> Path:
        """Save a report to file."""
        path = self._log_dir / f"report_{name}_{datetime.now(UTC).strftime('%Y%m%d')}.json"
        with open(path, "w") as f:
            json.dump(report, f, indent=2)
        return path