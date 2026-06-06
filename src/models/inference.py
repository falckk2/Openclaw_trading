"""Model inference — runs trained models on live data."""

from .base import ModelBase
from .features.feature_builder import FeatureBuilder
from ..data.dataclasses import Candle


class ModelInference:
    """Runs model inference on candle data."""

    def __init__(self, model: ModelBase, feature_builder: FeatureBuilder | None = None):
        self._model = model
        self._feature_builder = feature_builder or FeatureBuilder()

    async def predict(self, candles: list[Candle]) -> dict:
        """
        Run inference on candles and return prediction with metadata.
        """
        features = self._feature_builder.build_features(candles)

        # Ensure we have enough data
        if len(features) < 50:
            return {"action": "hold", "confidence": 0.0, "reason": "insufficient_data"}

        # Use only the most recent features for prediction
        X = features[-1:]  # single row prediction
        raw_pred = self._model.predict(X)

        # Convert raw prediction to action
        action_idx = int(raw_pred[0])
        action_map = {0: "sell", 1: "hold", 2: "buy"}
        action = action_map.get(action_idx, "hold")
        confidence = float(raw_pred[1]) if len(raw_pred.shape) > 1 else 0.5

        return {
            "action": action,
            "confidence": confidence,
            "model": self._model.name,
            "version": self._model.version,
            "raw_prediction": raw_pred.tolist(),
        }