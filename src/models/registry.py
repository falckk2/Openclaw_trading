"""Model registry — versioned model storage and loading."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import ModelBase


@dataclass
class ModelInfo:
    """Metadata about a registered model."""
    name: str
    version: str
    path: Path
    trained_at: str
    accuracy: float | None = None


class ModelRegistry:
    """
    Manages model versions — stores trained models and provides loading.
    Models are saved as pickled files with metadata JSON.
    """

    def __init__(self, registry_dir: Path | str = "models/registry"):
        self._registry_dir = Path(registry_dir)
        self._registry_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._registry_dir / "index.json"
        self._index: dict[str, ModelInfo] = {}
        self._load_index()

    def _load_index(self) -> None:
        """Load the registry index."""
        if self._index_path.exists():
            with open(self._index_path) as f:
                data = json.load(f)
                self._index = {
                    k: ModelInfo(**v) for k, v in data.items()
                }

    def _save_index(self) -> None:
        """Save the registry index."""
        data = {k: {
            "name": v.name,
            "version": v.version,
            "path": str(v.path),
            "trained_at": v.trained_at,
            "accuracy": v.accuracy,
        } for k, v in self._index.items()}
        with open(self._index_path, "w") as f:
            json.dump(data, f, indent=2)

    def register(self, model: ModelBase, trained_at: str, accuracy: float | None = None) -> None:
        """Register a new model version."""
        key = f"{model.name}:{model.version}"
        model_dir = self._registry_dir / model.name / model.version
        model_dir.mkdir(parents=True, exist_ok=True)

        info = ModelInfo(
            name=model.name,
            version=model.version,
            path=model_dir,
            trained_at=trained_at,
            accuracy=accuracy,
        )
        self._index[key] = info
        self._save_index()

    def load(self, name: str, version: str) -> ModelBase | None:
        """
        Load a model from registry.
        Note: actual loading depends on model format — stub for now.
        """
        key = f"{name}:{version}"
        info = self._index.get(key)
        if not info:
            return None

        # TODO: implement actual model loading (pickle/onnx/etc)
        return None

    def list_models(self) -> list[ModelInfo]:
        """List all registered models."""
        return list(self._index.values())

    def get_latest(self, name: str) -> ModelInfo | None:
        """Get the latest version of a model by name."""
        versions = [v for k, v in self._index.items() if v.name == name]
        if not versions:
            return None
        return sorted(versions, key=lambda v: v.version)[-1]