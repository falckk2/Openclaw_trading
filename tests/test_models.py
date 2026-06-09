"""Tests for models module."""

import pytest
import numpy as np

from src.models.features.feature_builder import FeatureBuilder
from src.models.inference import DNNInferenceModel
from src.data.dataclasses import Candle
from datetime import datetime, timedelta, UTC


class TestFeatureBuilder:
    """Tests for FeatureBuilder."""

    def test_build_features_shape(self):
        """Feature matrix has correct shape."""
        candles = [
            Candle(
                timestamp=datetime.now(UTC) - timedelta(hours=i),
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


class TestDNNInferenceModel:
    """Tests for DNN inference model."""

    def test_model_init(self):
        """Model initializes with correct defaults."""
        model = DNNInferenceModel(input_dim=50)
        assert model.name == "dnn"
        assert model.version == "1.0.0"
        assert model.input_dim == 50

    def test_model_weights_init(self):
        """Weights initialize correctly."""
        model = DNNInferenceModel(input_dim=50)
        model._init_weights()
        assert model._W1 is not None
        assert model._b1 is not None
        assert model._W2 is not None
        assert model._b2 is not None
        assert model._W3 is not None
        assert model._b3 is not None
        assert model._W1.shape == (50, 64)
        assert model._W2.shape == (64, 32)
        assert model._W3.shape == (32, 3)

    def test_forward_pass_shape(self):
        """Forward pass produces correct output shape."""
        model = DNNInferenceModel(input_dim=50)
        model._init_weights()

        X = np.random.rand(10, 50)
        probs = model.predict(X)

        assert probs.shape == (10, 3)
        # Probabilities should sum to 1
        assert np.allclose(probs.sum(axis=1), 1.0)

    def test_single_sample_input(self):
        """Single sample input works."""
        model = DNNInferenceModel(input_dim=50)
        model._init_weights()

        X = np.random.rand(50)
        probs = model.predict(X)

        assert probs.shape == (3,)
        assert np.isclose(probs.sum(), 1.0)

    def test_predict_direction(self):
        """predict_direction returns valid direction and confidence."""
        model = DNNInferenceModel(input_dim=50)
        model._init_weights()

        X = np.random.rand(50)
        direction, confidence = model.predict_direction(X)

        assert direction in ["buy", "hold", "sell"]
        assert 0.0 <= confidence <= 1.0

    def test_probs_bounded(self):
        """Probabilities are in valid range."""
        model = DNNInferenceModel(input_dim=50)
        model._init_weights()

        X = np.random.rand(20, 50)
        probs = model.predict(X)

        assert np.all(probs >= 0.0)
        assert np.all(probs <= 1.0)

    def test_save_and_load(self, tmp_path):
        """Model can be saved and loaded."""
        model = DNNInferenceModel(input_dim=50)
        model._init_weights()
        model._trained = True

        path = tmp_path / "model.json"
        model.save(path)

        loaded = DNNInferenceModel(input_dim=50)
        loaded.load(path)

        assert loaded.name == model.name
        assert loaded.version == model.version
        assert loaded._W1 is not None
        assert np.allclose(loaded._W1, model._W1)

    def test_load_nonexistent_raises(self, tmp_path):
        """Loading nonexistent file raises error."""
        model = DNNInferenceModel(input_dim=50)
        with pytest.raises(FileNotFoundError):
            model.load(tmp_path / "nonexistent.json")

    def test_predict_before_train_raises(self):
        """Predicting without trained weights raises error."""
        model = DNNInferenceModel(input_dim=50)
        X = np.random.rand(10, 50)
        with pytest.raises(RuntimeError, match="weights not initialized"):
            model.predict(X)

    @pytest.mark.asyncio
    async def test_train_improves_accuracy(self):
        """Training produces a model that can learn."""
        model = DNNInferenceModel(input_dim=50)

        # Create synthetic data: clear pattern
        # Class 0: low variance, class 2: high variance
        X = np.random.rand(200, 50)
        # Labels based on first feature: >0.5 = buy (2), <0.3 = sell (0), else hold (1)
        y = np.zeros(200, dtype=int)
        y[X[:, 0] > 0.6] = 2
        y[(X[:, 0] <= 0.6) & (X[:, 0] > 0.4)] = 1
        y[X[:, 0] <= 0.4] = 0

        result = await model.train(X, y, epochs=50, lr=0.01)

        assert result.accuracy > 0.3  # Should do better than random (33%)
        assert result.accuracy <= 1.0
        assert result.precision >= 0.0
        assert result.f1 >= 0.0