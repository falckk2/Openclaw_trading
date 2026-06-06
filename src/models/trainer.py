"""Model trainer — offline training of ML/DL models."""

import numpy as np
from datetime import datetime

from .base import ModelBase, TrainingResult


class ModelTrainer:
    """Handles offline training of models on historical data."""

    async def train(
        self,
        model: ModelBase,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray | None = None,
        y_val: np.ndarray | None = None,
    ) -> TrainingResult:
        """
        Train a model and return training metrics.
        """
        import time

        start = time.time()
        result = await model.train(X_train, y_train)
        training_time = time.time() - start

        return TrainingResult(
            model_version=model.version,
            accuracy=result.accuracy if hasattr(result, "accuracy") else 0.0,
            precision=result.precision if hasattr(result, "precision") else 0.0,
            recall=result.recall if hasattr(result, "recall") else 0.0,
            f1=result.f1 if hasattr(result, "f1") else 0.0,
            training_time_seconds=training_time,
        )

    @staticmethod
    def prepare_labels(candles: list, forward_periods: int = 5, threshold_pct: float = 0.01) -> np.ndarray:
        """
        Create labels from candle data.
        - 0 = sell (price drops > threshold)
        - 1 = hold
        - 2 = buy (price rises > threshold)
        """
        closes = np.array([c.close for c in candles])
        labels = np.zeros(len(closes) - forward_periods, dtype=int)

        for i in range(len(labels)):
            future_return = (closes[i + forward_periods] - closes[i]) / closes[i]
            if future_return > threshold_pct:
                labels[i] = 2  # buy
            elif future_return < -threshold_pct:
                labels[i] = 0  # sell
            else:
                labels[i] = 1  # hold

        return labels