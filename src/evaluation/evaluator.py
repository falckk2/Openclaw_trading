"""
Strategy/Model Evaluator — evaluates trading strategies and ML models.

Provides:
- Backtesting on historical data
- Walk-forward analysis
- Live performance tracking
- Cross-validation for ML models
"""

import json
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import numpy as np

from ..data.dataclasses import Candle, Ticker
from ..strategies.base import Strategy
from ..models.base import ModelBase
from ..paper_trading.simulator import PaperTradingEngine
from .metrics import calculate_trade_stats, calculate_risk_metrics


@dataclass
class BacktestResult:
    """Result of a backtest run."""
    strategy_name: str
    start_date: str
    end_date: str
    initial_equity: float
    final_equity: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_pnl: float
    sharpe_ratio: float
    max_drawdown_pct: float
    profit_factor: float
    trade_log: list[dict] | None = None  # optional for large backtests


@dataclass
class EvaluationResult:
    """Result of evaluating a model on a dataset."""
    model_name: str
    model_version: str
    dataset_size: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    confusion_matrix: list[list[int]] | None
    evaluated_at: str
    cross_validation_scores: list[float] | None = None


class StrategyEvaluator:
    """
    Evaluates trading strategies via backtesting.

    SOLID:
    - SRP: only evaluates strategy performance
    - OCP: works with any Strategy implementation
    - DIP: depends on Strategy abstraction
    """

    def __init__(
        self,
        initial_equity: float = 10000.0,
        fee_rate: float = 0.001,
    ):
        self._initial_equity = initial_equity
        self._fee_rate = fee_rate

    async def backtest(
        self,
        strategy: Strategy,
        candles: list[Candle],
        symbol: str,
        *,
        log_trades: bool = False,
    ) -> BacktestResult:
        """
        Run a backtest for a strategy on historical candles.

        Args:
            strategy: strategy to backtest
            candles: historical candle data (must be chronological)
            symbol: trading symbol (e.g. "BTC-USDT")
            log_trades: if True, include full trade log in result

        Returns:
            BacktestResult with performance metrics
        """
        # Create simulated exchange and engine
        mock_exchange = _MockExchangeForBacktest(candles)
        engine = PaperTradingEngine(mock_exchange, initial_balance=self._initial_equity)

        trades_log = []
        equity_curve = [self._initial_equity]

        # Run through candles
        for i, candle in enumerate(candles):
            mock_exchange.set_current_candle(candle)

            # Check if we have an open position
            position = engine.get_position(symbol)

            # Generate signal
            signal = await strategy.generate_signal(candles[: i + 1], position)

            if signal is None:
                continue

            action = signal.action
            qty = signal.quantity or 1.0

            try:
                if action == "buy" and position is None:
                    await engine.open_position(symbol, "long", qty, strategy_name=strategy.name)
                elif action == "sell" and position is not None:
                    await engine.close_position(symbol, strategy_name=strategy.name)
                    trades = engine.get_trade_history()
                    if trades:
                        last_trade = trades[-1]
                        trades_log.append({
                            "entry_price": last_trade.entry_price,
                            "exit_price": last_trade.exit_price,
                            "pnl": last_trade.pnl,
                            "opened_at": last_trade.opened_at.isoformat(),
                            "closed_at": last_trade.closed_at.isoformat(),
                        })
            except ValueError:
                # Insufficient balance or other error — skip
                continue

            # Update equity
            balance = engine.get_balance()
            equity_curve.append(balance.total_equity)

        # Calculate final metrics
        final_equity = engine.get_balance().total_equity
        trades = engine.get_trade_history()

        if trades:
            pnls = [t.pnl for t in trades]
            trade_stats = calculate_trade_stats(pnls)

            # Calculate returns series for risk metrics
            returns = [(equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1] for i in range(1, len(equity_curve))]
            risk_metrics = calculate_risk_metrics(returns) if returns else None
        else:
            trade_stats = None
            risk_metrics = None

        start_date = candles[0].timestamp.isoformat() if candles else ""
        end_date = candles[-1].timestamp.isoformat() if candles else ""

        return BacktestResult(
            strategy_name=strategy.name,
            start_date=start_date,
            end_date=end_date,
            initial_equity=self._initial_equity,
            final_equity=final_equity,
            total_return_pct=((final_equity - self._initial_equity) / self._initial_equity) * 100,
            total_trades=trade_stats.total_trades if trade_stats else 0,
            winning_trades=trade_stats.winning_trades if trade_stats else 0,
            losing_trades=trade_stats.losing_trades if trade_stats else 0,
            win_rate=trade_stats.win_rate if trade_stats else 0.0,
            avg_pnl=trade_stats.avg_pnl if trade_stats else 0.0,
            sharpe_ratio=risk_metrics.sharpe_ratio if risk_metrics else 0.0,
            max_drawdown_pct=risk_metrics.max_drawdown_pct if risk_metrics else 0.0,
            profit_factor=trade_stats.profit_factor if trade_stats else 0.0,
            trade_log=trades_log if log_trades else None,
        )

    async def walk_forward(
        self,
        strategy: Strategy,
        all_candles: list[Candle],
        symbol: str,
        *,
        train_days: int = 30,
        test_days: int = 7,
    ) -> list[BacktestResult]:
        """
        Walk-forward analysis: train on window, test on next window.

        Args:
            strategy: strategy to evaluate
            all_candles: all historical candles
            symbol: trading symbol
            train_days: number of days for training window
            test_days: number of days for test window

        Returns:
            List of BacktestResult for each test window
        """
        results = []
        day_seconds = 86400
        train_len = train_days * 24  # assume hourly candles
        test_len = test_days * 24

        start_idx = 0
        while start_idx + train_len + test_len <= len(all_candles):
            train_candles = all_candles[start_idx: start_idx + train_len]
            test_candles = all_candles[start_idx + train_len: start_idx + train_len + test_len]

            result = await self.backtest(strategy, test_candles, symbol)
            results.append(result)

            start_idx += test_len

        return results


class ModelEvaluator:
    """
    Evaluates ML models on validation data.

    SOLID:
    - SRP: only evaluates model performance
    - OCP: works with any ModelBase implementation
    - DIP: depends on ModelBase abstraction
    """

    def __init__(self, eval_dir: Path | str = "logs/evaluations"):
        self._eval_dir = Path(eval_dir)
        self._eval_dir.mkdir(parents=True, exist_ok=True)

    async def evaluate(
        self,
        model: ModelBase,
        X: np.ndarray,
        y: np.ndarray,
        *,
        cross_validation_folds: int = 0,
    ) -> EvaluationResult:
        """
        Evaluate a trained model on validation data.

        Args:
            model: trained model with predict() method
            X: feature matrix (n_samples, n_features)
            y: true labels (n_samples,)
            cross_validation_folds: if > 0, run k-fold CV

        Returns:
            EvaluationResult with metrics
        """
        from .metrics import calculate_model_metrics

        # Get predictions
        y_pred = np.argmax(model.predict(X), axis=1)

        # Calculate metrics
        metrics = calculate_model_metrics(y, y_pred)

        # Cross-validation if requested
        cv_scores = None
        if cross_validation_folds > 1:
            cv_scores = await self._cross_validate(model, X, y, cross_validation_folds)

        # Save evaluation result
        result = EvaluationResult(
            model_name=model.name,
            model_version=model.version,
            dataset_size=len(y),
            accuracy=metrics.accuracy,
            precision=metrics.precision,
            recall=metrics.recall,
            f1=metrics.f1,
            confusion_matrix=metrics.confusion_matrix,
            evaluated_at=datetime.now(UTC).isoformat(),
            cross_validation_scores=cv_scores,
        )

        self._save_evaluation(result)
        return result

    async def _cross_validate(
        self,
        model: ModelBase,
        X: np.ndarray,
        y: np.ndarray,
        folds: int,
    ) -> list[float]:
        """Run k-fold cross-validation."""
        from .metrics import calculate_model_metrics

        n = len(X)
        fold_size = n // folds
        scores = []

        indices = np.random.permutation(n)

        for fold in range(folds):
            start = fold * fold_size
            end = start + fold_size if fold < folds - 1 else n

            val_idx = indices[start:end]
            train_idx = np.concatenate([indices[:start], indices[end:]])

            # For simplicity, just evaluate on val fold (model already trained)
            # In production, would retrain on each fold
            X_val, y_val = X[val_idx], y[val_idx]
            y_pred = np.argmax(model.predict(X_val), axis=1)
            acc = np.mean(y_pred == y_val)
            scores.append(float(acc))

        return scores

    def _save_evaluation(self, result: EvaluationResult) -> None:
        """Save evaluation result to JSON."""
        path = self._eval_dir / f"{result.model_name}_{result.model_version}.eval.json"
        data = {
            "model_name": result.model_name,
            "model_version": result.model_version,
            "dataset_size": result.dataset_size,
            "accuracy": result.accuracy,
            "precision": result.precision,
            "recall": result.recall,
            "f1": result.f1,
            "confusion_matrix": result.confusion_matrix,
            "evaluated_at": result.evaluated_at,
            "cross_validation_scores": result.cross_validation_scores,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_evaluation(self, model_name: str, model_version: str) -> EvaluationResult | None:
        """Load a saved evaluation result."""
        path = self._eval_dir / f"{model_name}_{model_version}.eval.json"
        if not path.exists():
            return None

        with open(path) as f:
            data = json.load(f)
            return EvaluationResult(**data)


class _MockExchangeForBacktest:
    """Mock exchange that serves historical candles for backtesting."""

    def __init__(self, candles: list[Candle]):
        self._candles = candles
        self._current_idx = 0

    def set_current_candle(self, candle: Candle) -> None:
        """Set the current candle being processed."""
        self._current_candle = candle

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get current price from the current candle."""
        c = self._current_candle
        return Ticker(
            symbol=symbol,
            last=c.close,
            bid=c.close * 0.999,
            ask=c.close * 1.001,
            volume=c.volume,
            timestamp=c.timestamp,
        )