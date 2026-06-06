"""Base model class for ML/DL models."""

from abc import ABC, abstractmethod
import numpy as np


@dataclass
class TrainingResult:
    """Result of a model training run."""
    model_version: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    training_time_seconds: float


from dataclasses import dataclass as dc


class ModelBase(ABC):
    """Abstract base class for all ML/DL models."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Model name."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Model version."""

    @abstractmethod
    def predict(self, features: np.ndarray) -> np.ndarray:
        """Make predictions on input features."""

    @abstractmethod
    async def train(
        self, X: np.ndarray, y: np.ndarray
    ) -> TrainingResult:
        """Train the model on X (features) and y (labels)."""