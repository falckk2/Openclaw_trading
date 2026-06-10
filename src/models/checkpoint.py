"""
Model checkpoint manager — saves/loads trained model snapshots with metadata.

Provides:
- Versioned model checkpoints with training metrics
- Best model tracking (by specified metric)
- Training history with learning curves
- Model comparison based on saved checkpoints
"""

import json
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import numpy as np

from .base import ModelBase, TrainingResult


@dataclass
class CheckpointInfo:
    """Metadata for a saved model checkpoint."""
    checkpoint_id: str
    model_name: str
    model_version: str
    checkpoint_path: Path
    trained_at: str
    accuracy: float | None
    precision: float | None
    recall: float | None
    f1: float | None
    training_time_seconds: float
    dataset_info: dict[str, Any] | None = None
    epochs_trained: int | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "checkpoint_path": str(self.checkpoint_path),
            "trained_at": self.trained_at,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "training_time_seconds": self.training_time_seconds,
            "dataset_info": self.dataset_info,
            "epochs_trained": self.epochs_trained,
            "notes": self.notes,
        }


class CheckpointManager:
    """
    Manages model checkpoints with metadata.

    Saves:
    - Model weights (via model.save())
    - Training metadata (accuracy, precision, recall, f1, time)
    - Dataset info (size, date range)
    - Training history (optional)

    SOLID:
    - SRP: only manages checkpoint persistence and metadata
    - OCP: works with any ModelBase implementation
    - DIP: depends on ModelBase abstraction, not concrete models
    """

    CHECKPOINT_INDEX = "checkpoints.json"

    def __init__(self, checkpoint_dir: Path | str = "models/checkpoints"):
        self._checkpoint_dir = Path(checkpoint_dir)
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._checkpoint_dir / self.CHECKPOINT_INDEX
        self._checkpoints: dict[str, CheckpointInfo] = {}
        self._load_index()

    def _load_index(self) -> None:
        """Load checkpoint index from disk."""
        if self._index_path.exists():
            with open(self._index_path) as f:
                data = json.load(f)
                self._checkpoints = {
                    k: CheckpointInfo(**v) for k, v in data.items()
                }

    def _save_index(self) -> None:
        """Save checkpoint index to disk."""
        data = {k: v.to_dict() for k, v in self._checkpoints.items()}
        with open(self._index_path, "w") as f:
            json.dump(data, f, indent=2)

    def save(
        self,
        model: ModelBase,
        training_result: TrainingResult,
        *,
        dataset_info: dict[str, Any] | None = None,
        epochs_trained: int | None = None,
        notes: str = "",
    ) -> CheckpointInfo:
        """
        Save a model checkpoint with metadata.

        Args:
            model: trained model (must have save() method)
            training_result: result from model.train()
            dataset_info: optional info about training data (e.g. {"n_samples": 1000, "date_range": "..."})
            epochs_trained: number of epochs trained
            notes: optional notes about this checkpoint

        Returns:
            CheckpointInfo with saved metadata
        """
        # Create unique checkpoint ID
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        checkpoint_id = f"{model.name}_{model.version}_{timestamp}"

        # Create model-specific directory
        model_dir = self._checkpoint_dir / model.name / model.version
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save model weights
        weight_path = model_dir / f"{timestamp}.weights.json"
        model.save(weight_path)

        # Create checkpoint info
        info = CheckpointInfo(
            checkpoint_id=checkpoint_id,
            model_name=model.name,
            model_version=model.version,
            checkpoint_path=weight_path,
            trained_at=datetime.now(UTC).isoformat(),
            accuracy=training_result.accuracy,
            precision=training_result.precision,
            recall=training_result.recall,
            f1=training_result.f1,
            training_time_seconds=training_result.training_time_seconds,
            dataset_info=dataset_info,
            epochs_trained=epochs_trained,
            notes=notes,
        )

        self._checkpoints[checkpoint_id] = info
        self._save_index()

        # Update "latest" symlink for this model
        latest_link = model_dir / "latest.weights.json"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(weight_path.name)

        return info

    def load(self, checkpoint_id: str, model: ModelBase) -> None:
        """
        Load model weights from a checkpoint.

        Args:
            checkpoint_id: ID of checkpoint to load
            model: model instance to populate (must have load() method)
        """
        info = self._checkpoints.get(checkpoint_id)
        if not info:
            raise KeyError(f"Checkpoint not found: {checkpoint_id}")
        model.load(info.checkpoint_path)

    def load_latest(self, model_name: str, model: ModelBase) -> CheckpointInfo | None:
        """
        Load the latest checkpoint for a model name.

        Returns None if no checkpoint exists.
        """
        checkpoints = self.get_checkpoints(model_name)
        if not checkpoints:
            return None

        latest = max(checkpoints, key=lambda c: c.trained_at)
        self.load(latest.checkpoint_id, model)
        return latest

    def get_checkpoints(self, model_name: str | None = None) -> list[CheckpointInfo]:
        """
        Get all checkpoints, optionally filtered by model name.

        Returns sorted by trained_at (newest first).
        """
        if model_name:
            filtered = [c for c in self._checkpoints.values() if c.model_name == model_name]
        else:
            filtered = list(self._checkpoints.values())

        return sorted(filtered, key=lambda c: c.trained_at, reverse=True)

    def get_best(
        self,
        model_name: str,
        metric: str = "accuracy",
        higher_is_better: bool = True,
    ) -> CheckpointInfo | None:
        """
        Get the best checkpoint for a model by a specific metric.

        Args:
            model_name: name of the model
            metric: one of "accuracy", "precision", "recall", "f1"
            higher_is_better: True for accuracy/f1, False for loss

        Returns None if no checkpoints exist.
        """
        checkpoints = self.get_checkpoints(model_name)
        if not checkpoints:
            return None

        valid = [c for c in checkpoints if getattr(c, metric, None) is not None]
        if not valid:
            return None

        return max(valid, key=lambda c: getattr(c, metric, 0) if higher_is_better else -getattr(c, metric, 0))

    def compare_checkpoints(
        self,
        model_name: str,
        metric: str = "accuracy",
    ) -> list[dict[str, Any]]:
        """
        Compare all checkpoints for a model, ranked by metric.

        Returns list of dicts with checkpoint info and metric value.
        """
        checkpoints = self.get_checkpoints(model_name)
        if not checkpoints:
            return []

        valid = [c for c in checkpoints if getattr(c, metric, None) is not None]
        ranked = sorted(valid, key=lambda c: getattr(c, metric, 0), reverse=True)

        return [
            {
                "checkpoint_id": c.checkpoint_id,
                "model_version": c.model_version,
                "trained_at": c.trained_at,
                "accuracy": c.accuracy,
                "precision": c.precision,
                "recall": c.recall,
                "f1": c.f1,
                "training_time_seconds": c.training_time_seconds,
                "epochs_trained": c.epochs_trained,
                "notes": c.notes,
            }
            for c in ranked
        ]

    def delete_checkpoint(self, checkpoint_id: str) -> None:
        """Delete a checkpoint and its weights file."""
        info = self._checkpoints.pop(checkpoint_id, None)
        if info:
            # Remove weight file
            if info.checkpoint_path.exists():
                info.checkpoint_path.unlink()
            self._save_index()

    def get_training_history(self, model_name: str) -> list[dict[str, Any]]:
        """
        Get training history for a model (all checkpoints sorted by time).
        Useful for learning curves.
        """
        checkpoints = self.get_checkpoints(model_name)
        return [
            {
                "trained_at": c.trained_at,
                "accuracy": c.accuracy,
                "f1": c.f1,
                "precision": c.precision,
                "recall": c.recall,
                "training_time_seconds": c.training_time_seconds,
                "epochs_trained": c.epochs_trained,
                "notes": c.notes,
            }
            for c in checkpoints
        ]