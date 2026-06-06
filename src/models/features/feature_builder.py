"""Feature builder — transforms raw candles into model input features."""

import numpy as np
from typing import Sequence

from ...data.dataclasses import Candle


class FeatureBuilder:
    """Builds feature arrays from candle data for ML models."""

    @staticmethod
    def build_features(candles: Sequence[Candle]) -> np.ndarray:
        """
        Build a feature matrix from candles.
        Each row is a time step, columns are features.
        """
        closes = np.array([c.close for c in candles])
        highs = np.array([c.high for c in candles])
        lows = np.array([c.low for c in candles])
        volumes = np.array([c.volume for c in candles])

        features = np.column_stack([
            closes,  # 50
            highs,  # 50
            lows,  # 50
            volumes,  # 50
            np.pad(FeatureBuilder._returns(closes), (1, 0), constant_values=0),  # 50
            np.pad(FeatureBuilder._volatility(closes), (1, 0), constant_values=0),  # 50
            np.pad(FeatureBuilder._rsi(closes), (1, 0), constant_values=50),  # 50
            FeatureBuilder._moving_average(closes),  # 50 — already N elements
        ])
        return features

    @staticmethod
    def _returns(prices: np.ndarray, period: int = 1) -> np.ndarray:
        """Calculate returns."""
        return np.diff(prices, n=period) / prices[:-period]

    @staticmethod
    def _volatility(prices: np.ndarray, window: int = 14) -> np.ndarray:
        """Rolling volatility (std of returns)."""
        returns = FeatureBuilder._returns(prices)
        result = np.zeros_like(returns)
        for i in range(window, len(returns)):
            result[i] = np.std(returns[i - window:i])
        return result

    @staticmethod
    def _rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Relative Strength Index."""
        returns = FeatureBuilder._returns(prices)
        result = np.zeros_like(returns)
        for i in range(period, len(returns)):
            gains = returns[i - period:i].clip(min=0)
            losses = (-returns[i - period:i]).clip(min=0)
            avg_gain = np.mean(gains) if gains.any() else 0.001
            avg_loss = np.mean(losses) if losses.any() else 0.001
            rs = avg_gain / avg_loss
            result[i] = 100 - (100 / (1 + rs))
        return result

    @staticmethod
    def _moving_average(prices: np.ndarray, window: int = 20) -> np.ndarray:
        """Simple moving average."""
        result = np.zeros_like(prices)
        for i in range(window - 1, len(prices)):
            result[i] = np.mean(prices[i - window + 1:i + 1])
        return result