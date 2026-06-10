"""Evaluation module — strategy/model evaluation and leaderboard."""

from .evaluator import StrategyEvaluator, ModelEvaluator, BacktestResult, EvaluationResult
from .leaderboard import Leaderboard, AgentRanking
from .metrics import (
    TradeStats,
    RiskMetrics,
    ModelMetrics,
    calculate_trade_stats,
    calculate_risk_metrics,
    calculate_model_metrics,
    calculate_drawdown_series,
    max_drawdown,
)

__all__ = [
    "StrategyEvaluator",
    "ModelEvaluator",
    "BacktestResult",
    "EvaluationResult",
    "Leaderboard",
    "AgentRanking",
    "TradeStats",
    "RiskMetrics",
    "ModelMetrics",
    "calculate_trade_stats",
    "calculate_risk_metrics",
    "calculate_model_metrics",
    "calculate_drawdown_series",
    "max_drawdown",
]
