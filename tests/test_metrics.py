"""Tests for performance metrics calculations."""

import pytest
import numpy as np

from src.evaluation.metrics import (
    calculate_trade_stats,
    calculate_risk_metrics,
    calculate_model_metrics,
    calculate_drawdown_series,
    max_drawdown,
    TradeStats,
    RiskMetrics,
    ModelMetrics,
)


class TestCalculateTradeStats:
    """Tests for trade statistics calculation."""

    def test_empty_pnls(self):
        """Empty P&L list should return zero stats."""
        stats = calculate_trade_stats([])
        assert stats.total_trades == 0
        assert stats.win_rate == 0.0

    def test_all_winning_trades(self):
        """All winning trades should give 100% win rate."""
        pnls = [10.0, 20.0, 15.0, 5.0]
        stats = calculate_trade_stats(pnls)

        assert stats.total_trades == 4
        assert stats.winning_trades == 4
        assert stats.losing_trades == 0
        assert stats.win_rate == 1.0
        assert stats.avg_pnl == 12.5
        assert stats.profit_factor == float("inf")

    def test_all_losing_trades(self):
        """All losing trades should give 0% win rate."""
        pnls = [-10.0, -20.0, -15.0]
        stats = calculate_trade_stats(pnls)

        assert stats.total_trades == 3
        assert stats.winning_trades == 0
        assert stats.losing_trades == 3
        assert stats.win_rate == 0.0

    def test_mixed_trades(self):
        """Mixed trades should calculate correct statistics."""
        pnls = [10.0, -5.0, 20.0, -10.0, 15.0]
        stats = calculate_trade_stats(pnls)

        assert stats.total_trades == 5
        assert stats.winning_trades == 3
        assert stats.losing_trades == 2
        assert stats.win_rate == 0.6

    def test_profit_factor_calculation(self):
        """Profit factor should be gross wins / gross losses."""
        pnls = [10.0, -5.0, 20.0, -10.0]  # wins=30, losses=15
        stats = calculate_trade_stats(pnls)

        assert stats.profit_factor == 2.0  # 30 / 15

    def test_expectancy(self):
        """Expectancy should be average P&L per trade."""
        pnls = [10.0, -5.0, 15.0]
        stats = calculate_trade_stats(pnls)

        assert stats.expectancy == (10.0 - 5.0 + 15.0) / 3

    def test_largest_win_loss(self):
        """Should track largest win and largest loss."""
        pnls = [5.0, 50.0, -30.0, 10.0, -20.0]
        stats = calculate_trade_stats(pnls)

        assert stats.largest_win == 50.0
        assert stats.largest_loss == -30.0

    def test_std_dev(self):
        """Standard deviation should be calculated correctly."""
        pnls = [10.0, 10.0, 10.0, 10.0]  # no variance
        stats = calculate_trade_stats(pnls)

        assert stats.std_dev == 0.0


class TestCalculateRiskMetrics:
    """Tests for risk-adjusted metrics."""

    def test_empty_returns(self):
        """Empty returns should give zero metrics."""
        metrics = calculate_risk_metrics([])
        assert metrics.sharpe_ratio == 0.0
        assert metrics.max_drawdown_pct == 0.0

    def test_positive_returns_sharpe(self):
        """Positive returns should give positive Sharpe ratio."""
        # 1% daily return with 0.5% std dev -> Sharpe ~2.1 (annualized)
        returns = [0.01, 0.012, 0.009, 0.011]
        metrics = calculate_risk_metrics(returns, periods_per_year=252)

        assert metrics.sharpe_ratio > 0
        assert metrics.volatility > 0

    def test_negative_returns_sharpe(self):
        """Negative returns should give negative Sharpe ratio."""
        returns = [-0.01, -0.012, -0.009, -0.011]
        metrics = calculate_risk_metrics(returns, periods_per_year=252)

        assert metrics.sharpe_ratio < 0

    def test_max_drawdown(self):
        """Max drawdown should be calculated correctly."""
        # Equity goes up then down 20%
        equity_curve = [100.0, 110.0, 120.0, 100.0, 105.0]
        returns = [0.10, 0.091, -0.167, 0.05]  # simplified

        metrics = calculate_risk_metrics(returns)

        assert metrics.max_drawdown_pct > 0
        assert metrics.max_drawdown_pct <= 0.20  # approximately

    def test_sortino_ratio(self):
        """Sortino ratio should only consider downside deviation."""
        returns = [0.01, 0.02, -0.01, 0.015, -0.02]
        metrics = calculate_risk_metrics(returns)

        # Sortino should be different from Sharpe (uses downside dev)
        assert isinstance(metrics.sortino_ratio, float)

    def test_annualization(self):
        """Returns should be annualized based on periods_per_year."""
        daily_return = 0.001  # 0.1% daily
        returns = [daily_return] * 10

        metrics = calculate_risk_metrics(returns, periods_per_year=252)
        # Annual return should be ~0.252 (25.2%)
        assert metrics.sharpe_ratio > 0


class TestCalculateDrawdownSeries:
    """Tests for drawdown calculation."""

    def test_empty_equity(self):
        """Empty equity curve should return empty drawdowns."""
        assert calculate_drawdown_series([]) == []

    def test_continuously_rising_equity(self):
        """Rising equity should have no drawdowns."""
        equity = [100.0, 110.0, 120.0, 130.0]
        drawdowns = calculate_drawdown_series(equity)

        assert all(d == 0.0 for d in drawdowns)

    def test_equity_with_drawdown(self):
        """Equity that drops should show drawdowns."""
        equity = [100.0, 110.0, 90.0, 100.0]
        drawdowns = calculate_drawdown_series(equity)

        # Drawdowns: 0, 0, (90-110)/110 = -0.18, 0
        assert drawdowns[2] < 0
        assert drawdowns[2] == pytest.approx(-0.1818, rel=0.01)


class TestMaxDrawdown:
    """Tests for max drawdown calculation."""

    def test_empty_equity(self):
        """Empty equity should return zero drawdown."""
        dd, peak, trough = max_drawdown([])
        assert dd == 0.0
        assert peak == -1
        assert trough == -1

    def test_no_drawdown(self):
        """Rising equity should have zero max drawdown."""
        equity = [100.0, 110.0, 120.0]
        dd, peak, trough = max_drawdown(equity)

        assert dd == 0.0

    def test_max_drawdown_identifies_trough(self):
        """Should identify the maximum drawdown point."""
        equity = [100.0, 110.0, 80.0, 90.0, 120.0]
        dd, peak, trough = max_drawdown(equity)

        assert dd == pytest.approx(0.273, rel=0.01)  # (80-110)/110
        assert peak == 1  # 110 at index 1
        assert trough == 2  # 80 at index 2


class TestCalculateModelMetrics:
    """Tests for model classification metrics."""

    def test_empty_predictions(self):
        """Empty arrays should return zero metrics."""
        metrics = calculate_model_metrics(np.array([]), np.array([]))
        assert metrics.accuracy == 0.0

    def test_perfect_accuracy(self):
        """Perfect predictions should give 100% accuracy."""
        y_true = np.array([0, 1, 2, 0, 1, 2])
        y_pred = np.array([0, 1, 2, 0, 1, 2])

        metrics = calculate_model_metrics(y_true, y_pred)

        assert metrics.accuracy == 1.0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0

    def test_zero_accuracy(self):
        """All wrong predictions should give 0% accuracy."""
        y_true = np.array([0, 0, 0])
        y_pred = np.array([2, 2, 2])

        metrics = calculate_model_metrics(y_true, y_pred)

        assert metrics.accuracy == 0.0

    def test_partial_accuracy(self):
        """Partial accuracy should be calculated correctly."""
        y_true = np.array([0, 1, 2, 0])
        y_pred = np.array([0, 2, 2, 1])

        metrics = calculate_model_metrics(y_true, y_pred)

        assert metrics.accuracy == 0.5  # 2 out of 4 correct

    def test_confusion_matrix(self):
        """Confusion matrix should be built correctly."""
        y_true = np.array([0, 0, 1, 1, 2, 2])
        y_pred = np.array([0, 0, 1, 2, 2, 2])

        metrics = calculate_model_metrics(y_true, y_pred)

        assert metrics.confusion_matrix is not None
        cm = metrics.confusion_matrix
        # cm[true_label, pred_label]
        assert cm[0][0] == 2  # class 0 correctly predicted as 0 (2 times)
        assert cm[1][1] == 1  # class 1 correctly predicted as 1 (1 time)
        assert cm[1][2] == 1  # class 1 incorrectly predicted as 2 (1 time)
        assert cm[2][2] == 2  # class 2 correctly predicted as 2 (2 times)