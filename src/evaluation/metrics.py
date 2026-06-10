"""
Trading and model performance metrics.

Provides:
- Risk-adjusted return metrics (Sharpe, Sortino, Calmar)
- Drawdown analysis (max drawdown, recovery time)
- Trade statistics (win rate, profit factor, expectancy)
- Model evaluation metrics (accuracy, precision, recall, F1, AUC)
"""

import numpy as np
from dataclasses import dataclass
from typing import Literal


@dataclass
class TradeStats:
    """Statistical summary of a set of trades."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy: float
    largest_win: float
    largest_loss: float
    std_dev: float


@dataclass
class RiskMetrics:
    """Risk-adjusted performance metrics."""
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    calmar_ratio: float | None  # None if no annual return
    volatility: float


@dataclass
class ModelMetrics:
    """Classification model metrics."""
    accuracy: float
    precision: float
    recall: float
    f1: float
    confusion_matrix: list[list[int]] | None = None


def calculate_trade_stats(pnls: list[float]) -> TradeStats:
    """
    Calculate statistical summary from a list of trade P&Ls.

    Args:
        pnls: list of P&L values (positive = win, negative = loss)

    Returns:
        TradeStats with comprehensive trade statistics
    """
    if not pnls:
        return TradeStats(
            total_trades=0, winning_trades=0, losing_trades=0,
            win_rate=0.0, avg_pnl=0.0, avg_win=0.0, avg_loss=0.0,
            profit_factor=0.0, expectancy=0.0, largest_win=0.0,
            largest_loss=0.0, std_dev=0.0,
        )

    pnls = np.array(pnls)
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]

    total_trades = len(pnls)
    winning_trades = len(wins)
    losing_trades = len(losses)
    win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

    avg_pnl = np.mean(pnls)
    avg_win = np.mean(wins) if len(wins) > 0 else 0.0
    avg_loss = np.mean(losses) if len(losses) > 0 else 0.0

    total_wins = np.sum(wins) if len(wins) > 0 else 0.0
    total_losses = abs(np.sum(losses)) if len(losses) > 0 else 0.0
    profit_factor = total_wins / total_losses if total_losses > 0 else float("inf") if total_wins > 0 else 0.0

    expectancy = avg_pnl  # E[P&L] per trade

    largest_win = np.max(wins) if len(wins) > 0 else 0.0
    largest_loss = np.min(losses) if len(losses) > 0 else 0.0

    std_dev = np.std(pnls) if len(pnls) > 1 else 0.0

    return TradeStats(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate,
        avg_pnl=float(avg_pnl),
        avg_win=float(avg_win),
        avg_loss=float(avg_loss),
        profit_factor=float(profit_factor),
        expectancy=float(expectancy),
        largest_win=float(largest_win),
        largest_loss=float(largest_loss),
        std_dev=float(std_dev),
    )


def calculate_risk_metrics(
    returns: list[float],
    *,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> RiskMetrics:
    """
    Calculate risk-adjusted metrics from a series of returns.

    Args:
        returns: list of period returns (e.g. daily P&L as % of equity)
        risk_free_rate: annual risk-free rate (e.g. 0.02 for 2%)
        periods_per_year: number of periods in a year (252 for daily, 52 for weekly)

    Returns:
        RiskMetrics with Sharpe, Sortino, drawdown metrics
    """
    if not returns:
        return RiskMetrics(
            sharpe_ratio=0.0, sortino_ratio=0.0,
            max_drawdown=0.0, max_drawdown_pct=0.0,
            calmar_ratio=None, volatility=0.0,
        )

    rets = np.array(returns)
    n = len(rets)

    # Annualize returns and volatility
    avg_return = np.mean(rets) * periods_per_year
    volatility = np.std(rets) * np.sqrt(periods_per_year)

    # Sharpe ratio
    excess_return = avg_return - risk_free_rate
    sharpe = excess_return / volatility if volatility > 0 else 0.0

    # Sortino ratio (downside deviation)
    downside_rets = rets[rets < 0]
    downside_std = np.std(downside_rets) * np.sqrt(periods_per_year) if len(downside_rets) > 1 else 0.0
    sortino = excess_return / downside_std if downside_std > 0 else 0.0

    # Max drawdown
    cumulative = 1 + np.cumsum(rets)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - running_max) / running_max
    max_drawdown_pct = abs(np.min(drawdowns)) if len(drawdowns) > 0 else 0.0
    max_drawdown = np.min(cumulative - running_max) if len(cumulative) > 0 else 0.0

    # Calmar ratio (annual return / max drawdown)
    annual_return = avg_return
    calmar = annual_return / max_drawdown_pct if max_drawdown_pct > 0 else None

    return RiskMetrics(
        sharpe_ratio=float(sharpe),
        sortino_ratio=float(sortino),
        max_drawdown=float(max_drawdown),
        max_drawdown_pct=float(max_drawdown_pct),
        calmar_ratio=float(calmar) if calmar is not None else None,
        volatility=float(volatility),
    )


def calculate_drawdown_series(equity_curve: list[float]) -> list[float]:
    """
    Calculate drawdown series from an equity curve.

    Args:
        equity_curve: list of equity values over time

    Returns:
        List of drawdown values (negative = drawdown) at each point
    """
    if not equity_curve:
        return []

    equity = np.array(equity_curve)
    running_max = np.maximum.accumulate(equity)
    drawdowns = (equity - running_max) / running_max
    return drawdowns.tolist()


def max_drawdown(equity_curve: list[float]) -> tuple[float, int, int]:
    """
    Find maximum drawdown and its duration.

    Args:
        equity_curve: list of equity values

    Returns:
        (max_drawdown_pct, peak_index, trough_index)
    """
    if not equity_curve:
        return 0.0, -1, -1

    equity = np.array(equity_curve)
    running_max = np.maximum.accumulate(equity)
    drawdowns = (equity - running_max) / running_max

    trough_idx = int(np.argmin(drawdowns))
    peak_before = int(np.argmax(equity[:trough_idx + 1]))
    max_dd = abs(drawdowns[trough_idx])

    return float(max_dd), int(peak_before), int(trough_idx)


def calculate_model_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    num_classes: int = 3,
) -> ModelMetrics:
    """
    Calculate classification metrics from true and predicted labels.

    Args:
        y_true: true labels
        y_pred: predicted labels
        num_classes: number of classes (default 3 for sell/hold/buy)

    Returns:
        ModelMetrics with accuracy, precision, recall, f1
    """
    n = len(y_true)
    if n == 0:
        return ModelMetrics(accuracy=0.0, precision=0.0, recall=0.0, f1=0.0)

    # Accuracy
    accuracy = np.mean(y_true == y_pred)

    # Per-class precision, recall, f1
    precisions, recalls, f1s = [], [], []
    cm = np.zeros((num_classes, num_classes), dtype=int)

    for i in range(n):
        cm[int(y_true[i]), int(y_pred[i])] += 1

    for c in range(num_classes):
        tp = cm[c, c]
        fp = np.sum(cm[:, c]) - tp
        fn = np.sum(cm[c, :]) - tp

        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0

        precisions.append(p)
        recalls.append(r)
        f1s.append(f)

    return ModelMetrics(
        accuracy=float(accuracy),
        precision=float(np.mean(precisions)),
        recall=float(np.mean(recalls)),
        f1=float(np.mean(f1s)),
        confusion_matrix=cm.tolist(),
    )


def calculate_auc_roc(y_true: np.ndarray, y_scores: np.ndarray, *, num_classes: int = 3) -> float:
    """
    Calculate AUC-ROC (one-vs-rest) for multi-class classification.

    Args:
        y_true: true labels (0 to num_classes-1)
        y_scores: predicted probabilities (n_samples, num_classes)
        num_classes: number of classes

    Returns:
        Average AUC across all classes (one-vs-rest)
    """
    from sklearn.metrics import roc_auc_score

    try:
        # One-vs-rest AUC
        return roc_auc_score(y_true, y_scores, multi_class="ovr", average="macro")
    except Exception:
        return 0.0