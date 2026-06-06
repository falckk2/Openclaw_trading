"""Tests for models module."""

import pytest
import numpy as np

from src.models.features.feature_builder import FeatureBuilder
from src.data.dataclasses import Candle
from datetime import datetime, timedelta


class TestFeatureBuilder:
    """Tests for FeatureBuilder."""

    def test_build_features_shape(self):
        """Feature matrix has correct shape."""
        candles = [
            Candle(
                timestamp=datetime.utcnow() - timedelta(hours=i),
                open=50000 + i * 10,
                high=50100 + i * 10,
                low=49900 + i * 10,
                close=50000 + i * 10,
                volume=1000,
            )
            for i in range(50)
        ]
        features = FeatureBuilder.build_features(candles)
        # Should have 50 rows and 8 feature columns
        assert features.shape[0] == 50
        assert features.shape[1] == 8

    def test_rsi_calculation(self):
        """RSI values are in valid range."""
        prices = np.array([100 + i * 2 for i in range(30)])
        rsi = FeatureBuilder._rsi(prices, period=14)
        valid_rsi = rsi[14:]  # Skip initial NaN values
        assert all(0 <= r <= 100 for r in valid_rsi if not np.isnan(r))

    def test_volatility_positive(self):
        """Volatility is always positive."""
        prices = np.array([100 + i * 2 for i in range(30)])
        vol = FeatureBuilder._volatility(prices, window=14)
        assert all(v >= 0 for v in vol[14:] if not np.isnan(v))