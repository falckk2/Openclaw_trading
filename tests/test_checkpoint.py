"""Tests for model checkpoint manager."""

import pytest
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import MagicMock

from src.models.checkpoint import CheckpointManager, CheckpointInfo
from src.models.base import TrainingResult


class MockModel:
    """Mock model for testing checkpoint save/load."""

    def __init__(self):
        self.name = "test_model"
        self.version = "1.0.0"
        self._weights = {"W1": [[1, 2], [3, 4]]}

    def save(self, path: Path) -> None:
        import json
        with open(path, "w") as f:
            json.dump({"weights": self._weights, "name": self.name, "version": self.version}, f)

    def load(self, path: Path) -> None:
        import json
        with open(path) as f:
            data = json.load(f)
            self._weights = data["weights"]
            self.name = data["name"]
            self.version = data["version"]


class TestCheckpointManager:
    """Tests for CheckpointManager."""

    @pytest.fixture
    def checkpoint_dir(self, tmp_path):
        return tmp_path / "checkpoints"

    @pytest.fixture
    def manager(self, checkpoint_dir):
        return CheckpointManager(checkpoint_dir=checkpoint_dir)

    @pytest.fixture
    def mock_model(self):
        return MockModel()

    @pytest.fixture
    def mock_result(self):
        return TrainingResult(
            model_version="test_model:1.0.0",
            accuracy=0.85,
            precision=0.82,
            recall=0.80,
            f1=0.81,
            training_time_seconds=120.5,
        )

    def test_save_creates_checkpoint(self, manager, mock_model, mock_result):
        """Saving a checkpoint should create files and update index."""
        info = manager.save(mock_model, mock_result)

        assert info.model_name == "test_model"
        assert info.model_version == "1.0.0"
        assert info.accuracy == 0.85
        assert info.checkpoint_path.exists()

    def test_load_restores_model(self, manager, mock_model, mock_result):
        """Loading a checkpoint should restore model weights."""
        info = manager.save(mock_model, mock_result)

        # Modify model to verify it gets overwritten
        mock_model._weights = {"W1": [[99, 99]]}

        manager.load(info.checkpoint_id, mock_model)
        assert mock_model._weights == {"W1": [[1, 2], [3, 4]]}

    def test_get_checkpoints_returns_sorted_list(self, manager, mock_model, mock_result):
        """Get checkpoints should return sorted list (newest first)."""
        for i in range(3):
            mock_model.version = f"1.0.{i}"
            manager.save(mock_model, mock_result)

        checkpoints = manager.get_checkpoints("test_model")
        assert len(checkpoints) == 3
        # Should be sorted by trained_at descending
        for i in range(len(checkpoints) - 1):
            assert checkpoints[i].trained_at >= checkpoints[i + 1].trained_at

    def test_get_best_by_metric(self, manager, mock_model, mock_result):
        """Get best should return checkpoint with highest metric value."""
        # Save multiple versions with different accuracy
        for acc in [0.70, 0.85, 0.78]:
            mock_result.accuracy = acc
            mock_model.version = f"1.0.{acc}"
            manager.save(mock_model, mock_result)

        best = manager.get_best("test_model", metric="accuracy")
        assert best.accuracy == 0.85

    def test_compare_checkpoints_ranked(self, manager, mock_model, mock_result):
        """Compare checkpoints should return ranked list sorted by metric."""
        for acc in [0.70, 0.85, 0.78]:
            mock_result.accuracy = acc
            mock_model.version = f"1.0.{acc}"
            manager.save(mock_model, mock_result)

        comparison = manager.compare_checkpoints("test_model", metric="accuracy")
        assert len(comparison) == 3
        assert comparison[0]["accuracy"] == 0.85  # highest accuracy first

    def test_delete_checkpoint_removes_files(self, manager, mock_model, mock_result):
        """Deleting a checkpoint should remove weight file and index entry."""
        info = manager.save(mock_model, mock_result)
        path = info.checkpoint_path

        assert path.exists()
        manager.delete_checkpoint(info.checkpoint_id)

        assert not path.exists()
        assert manager.get_checkpoints("test_model") == []

    def test_load_latest_returns_newest(self, manager, mock_model, mock_result):
        """Load latest should return the most recent checkpoint."""
        for i in range(3):
            mock_model.version = f"1.0.{i}"
            manager.save(mock_model, mock_result)

        latest = manager.load_latest("test_model", mock_model)
        assert latest is not None
        assert latest.model_version == "1.0.2"  # last saved

    def test_get_training_history(self, manager, mock_model, mock_result):
        """Get training history should return chronological list."""
        for acc in [0.70, 0.85, 0.78]:
            mock_result.accuracy = acc
            mock_model.version = f"1.0.{acc}"
            manager.save(mock_model, mock_result)

        history = manager.get_training_history("test_model")
        assert len(history) == 3
        # Should be ordered by trained_at (newest first)
        # Verify all expected keys are present
        for entry in history:
            assert "accuracy" in entry
            assert "trained_at" in entry


class TestCheckpointInfo:
    """Tests for CheckpointInfo dataclass."""

    def test_to_dict_serialization(self, tmp_path):
        """CheckpointInfo should serialize to dict correctly."""
        info = CheckpointInfo(
            checkpoint_id="test_1",
            model_name="model",
            model_version="1.0",
            checkpoint_path=tmp_path / "weights.json",
            trained_at="2024-01-01T00:00:00+00:00",
            accuracy=0.85,
            precision=0.82,
            recall=0.80,
            f1=0.81,
            training_time_seconds=100.0,
        )

        d = info.to_dict()
        assert d["checkpoint_id"] == "test_1"
        assert d["model_name"] == "model"
        assert d["accuracy"] == 0.85
        assert d["precision"] == 0.82