"""DNN inference model — simple 3-layer feedforward network for price direction."""

import json
import numpy as np
from pathlib import Path
from typing import Literal

from .base import ModelBase, TrainingResult


class DNNInferenceModel(ModelBase):
    """
    Simple 3-layer feedforward neural network for price direction prediction.

    Architecture:
        Input (n_features) -> Dense(64) -> ReLU -> Dense(32) -> ReLU -> Dense(3) -> Softmax
        Output: [prob_down, prob_hold, prob_up]

    Supports:
    - Loading pretrained weights from JSON
    - Inference on raw features
    - Direction prediction: "buy" (up), "hold", "sell" (down)
    """

    def __init__(
        self,
        input_dim: int = 50,
        hidden1_size: int = 64,
        hidden2_size: int = 32,
        output_size: int = 3,
    ):
        self.name = "dnn"
        self.version = "1.0.0"
        self.input_dim = input_dim
        self._hidden1_size = hidden1_size
        self._hidden2_size = hidden2_size
        self._output_size = output_size

        # Weight matrices and bias vectors
        # W1: (input_dim, hidden1_size), b1: (hidden1_size,)
        # W2: (hidden1_size, hidden2_size), b2: (hidden2_size,)
        # W3: (hidden2_size, output_size), b3: (output_size,)
        self._W1: np.ndarray | None = None
        self._b1: np.ndarray | None = None
        self._W2: np.ndarray | None = None
        self._b2: np.ndarray | None = None
        self._W3: np.ndarray | None = None
        self._b3: np.ndarray | None = None

        self._trained = False

    @property
    def version(self) -> str:
        return self._version

    @version.setter
    def version(self, v: str) -> None:
        self._version = v

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, n: str) -> None:
        self._name = n

    def _relu(self, x: np.ndarray) -> np.ndarray:
        """ReLU activation."""
        return np.maximum(0, x)

    def _relu_derivative(self, x: np.ndarray) -> np.ndarray:
        """Derivative of ReLU."""
        return (x > 0).astype(float)

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        """Softmax activation."""
        exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=-1, keepdims=True)

    def _init_weights(self, seed: int = 42) -> None:
        """Initialize weights with Xavier/He initialization."""
        rng = np.random.default_rng(seed)
        scale1 = np.sqrt(2.0 / self.input_dim)
        self._W1 = rng.standard_normal((self.input_dim, self._hidden1_size)).astype(np.float64) * scale1
        self._b1 = np.zeros(self._hidden1_size, dtype=np.float64)

        scale2 = np.sqrt(2.0 / self._hidden1_size)
        self._W2 = rng.standard_normal((self._hidden1_size, self._hidden2_size)).astype(np.float64) * scale2
        self._b2 = np.zeros(self._hidden2_size, dtype=np.float64)

        scale3 = np.sqrt(2.0 / self._hidden2_size)
        self._W3 = rng.standard_normal((self._hidden2_size, self._output_size)).astype(np.float64) * scale3
        self._b3 = np.zeros(self._output_size, dtype=np.float64)

    def _forward(self, X: np.ndarray) -> np.ndarray:
        """Forward pass through the network."""
        # Layer 1
        z1 = X @ self._W1 + self._b1
        a1 = self._relu(z1)

        # Layer 2
        z2 = a1 @ self._W2 + self._b2
        a2 = self._relu(z2)

        # Layer 3 (output)
        z3 = a2 @ self._W3 + self._b3
        probs = self._softmax(z3)

        return probs

    def predict(self, features: np.ndarray) -> np.ndarray:
        """
        Predict price direction probabilities.

        Args:
            features: 2D array (n_samples, n_features) or 1D (n_features,)

        Returns:
            2D array (n_samples, 3) with columns [prob_down, prob_hold, prob_up]
            Each row sums to 1.0
        """
        if self._W1 is None:
            raise RuntimeError("Model weights not initialized. Call load() or train() first.")

        # Handle single sample
        single_sample = features.ndim == 1
        if single_sample:
            features = features.reshape(1, -1)

        # Normalize features (standardization based on training stats)
        # Use simple min-max scaling per feature
        # For production, would load scaler params from training
        f_min = features.min(axis=0, keepdims=True)
        f_max = features.max(axis=0, keepdims=True)
        f_range = f_max - f_min
        f_range[f_range == 0] = 1.0  # avoid division by zero
        X_norm = (features - f_min) / f_range

        # Clip to [0, 1] range
        X_norm = np.clip(X_norm, 0, 1)

        probs = self._forward(X_norm)

        if single_sample:
            return probs[0]
        return probs

    def predict_direction(
        self, features: np.ndarray
    ) -> tuple[Literal["buy", "hold", "sell"], float]:
        """
        Predict the most likely direction.

        Returns:
            Tuple of (direction, confidence) where direction is "buy", "hold", or "sell"
            and confidence is the probability of that direction.
        """
        probs = self.predict(features)
        # probs = [prob_down, prob_hold, prob_up]
        direction_idx = int(np.argmax(probs))
        direction = ["sell", "hold", "buy"][direction_idx]
        confidence = float(probs[direction_idx])
        return direction, confidence

    async def train(
        self, X: np.ndarray, y: np.ndarray, *, epochs: int = 100, lr: float = 0.001
    ) -> TrainingResult:
        """
        Train the DNN using mini-batch gradient descent.

        Args:
            X: 2D feature array (n_samples, n_features)
            y: 1D label array (n_samples,) with values 0=sell, 1=hold, 2=buy

        Returns:
            TrainingResult with metrics
        """
        import time
        start = time.time()

        self._init_weights()
        self._trained = True

        # One-hot encode labels
        y_onehot = np.zeros((len(y), self._output_size), dtype=np.float64)
        for i, label in enumerate(y):
            y_onehot[i, int(label)] = 1.0

        n_samples = len(X)
        batch_size = min(32, n_samples)
        n_batches = max(1, n_samples // batch_size)

        for epoch in range(epochs):
            indices = np.random.permutation(n_samples)
            epoch_loss = 0.0

            for batch_start in range(0, n_samples, batch_size):
                batch_idx = indices[batch_start:batch_start + batch_size]
                X_batch = X[batch_idx]
                y_batch = y_onehot[batch_idx]

                # Forward pass
                z1 = X_batch @ self._W1 + self._b1
                a1 = self._relu(z1)
                z2 = a1 @ self._W2 + self._b2
                a2 = self._relu(z2)
                z3 = a2 @ self._W3 + self._b3
                probs = self._softmax(z3)

                # Cross-entropy loss
                eps = 1e-9
                loss = -np.mean(np.sum(y_batch * np.log(probs + eps), axis=1))
                epoch_loss += loss

                # Backward pass
                delta_output = probs - y_batch  # (batch, 3)
                dW3 = (a2.T @ delta_output) / batch_size
                db3 = np.mean(delta_output, axis=0)

                delta_hidden2 = delta_output @ self._W3.T * self._relu_derivative(z2)
                dW2 = (a1.T @ delta_hidden2) / batch_size
                db2 = np.mean(delta_hidden2, axis=0)

                delta_hidden1 = delta_hidden2 @ self._W2.T * self._relu_derivative(z1)
                dW1 = (X_batch.T @ delta_hidden1) / batch_size
                db1 = np.mean(delta_hidden1, axis=0)

                # Gradient clipping
                for dW in [dW1, dW2, dW3]:
                    np.clip(dW, -1.0, 1.0, out=dW)

                # Update weights
                self._W1 -= lr * dW1
                self._b1 -= lr * db1
                self._W2 -= lr * dW2
                self._b2 -= lr * db2
                self._W3 -= lr * dW3
                self._b3 -= lr * db3

            if epoch % 20 == 0:
                preds = np.argmax(probs, axis=1)
                acc = np.mean(preds == np.argmax(y_batch, axis=1))
                print(f"Epoch {epoch}/{epochs}, loss={epoch_loss/n_batches:.4f}, acc={acc:.3f}")

        # Final evaluation
        all_probs = self.predict(X)
        predictions = np.argmax(all_probs, axis=1)
        accuracy = np.mean(predictions == y)

        # Calculate precision, recall, f1 (macro)
        from collections import Counter
        precisions, recalls, f1s = [], [], []
        for c in range(3):
            tp = np.sum((predictions == c) & (y == c))
            fp = np.sum((predictions == c) & (y != c))
            fn = np.sum((predictions != c) & (y == c))
            p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
            precisions.append(p)
            recalls.append(r)
            f1s.append(f1)

        training_time = time.time() - start

        return TrainingResult(
            model_version=f"{self.name}:{self.version}",
            accuracy=float(accuracy),
            precision=float(np.mean(precisions)),
            recall=float(np.mean(recalls)),
            f1=float(np.mean(f1s)),
            training_time_seconds=training_time,
        )

    def save(self, path: Path | str) -> None:
        """Save model weights to a JSON file."""
        if self._W1 is None:
            raise RuntimeError("No weights to save — train or load first.")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "name": self.name,
            "version": self.version,
            "input_dim": int(self.input_dim),
            "hidden1_size": int(self._hidden1_size),
            "hidden2_size": int(self._hidden2_size),
            "output_size": int(self._output_size),
            "W1": self._W1.tolist(),
            "b1": self._b1.tolist(),
            "W2": self._W2.tolist(),
            "b2": self._b2.tolist(),
            "W3": self._W3.tolist(),
            "b3": self._b3.tolist(),
        }

        with open(path, "w") as f:
            json.dump(data, f)

    def load(self, path: Path | str) -> None:
        """Load model weights from a JSON file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        with open(path) as f:
            data = json.load(f)

        self.name = data["name"]
        self.version = data["version"]
        self.input_dim = data["input_dim"]
        self._hidden1_size = data["hidden1_size"]
        self._hidden2_size = data["hidden2_size"]
        self._output_size = data["output_size"]

        self._W1 = np.array(data["W1"], dtype=np.float64)
        self._b1 = np.array(data["b1"], dtype=np.float64)
        self._W2 = np.array(data["W2"], dtype=np.float64)
        self._b2 = np.array(data["b2"], dtype=np.float64)
        self._W3 = np.array(data["W3"], dtype=np.float64)
        self._b3 = np.array(data["b3"], dtype=np.float64)
        self._trained = True