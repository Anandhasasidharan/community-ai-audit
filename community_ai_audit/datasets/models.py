from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class DatasetInfo:
    """Metadata about a benchmark dataset."""

    name: str
    description: str
    version: str
    categories: List[str] = field(default_factory=list)
    num_samples: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "categories": self.categories,
            "num_samples": self.num_samples,
        }


@dataclass
class BenchmarkRun:
    """Record of a benchmark execution, persisted for trend analysis."""

    run_id: str = ""
    dataset_name: str = ""
    dataset_version: str = ""
    model_id: str = ""
    adapter_name: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    accuracy: float = 0.0
    scores: Dict[str, float] = field(default_factory=dict)
    num_samples: int = 0
    num_passed: int = 0
    num_failed: int = 0
    duration_seconds: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "model_id": self.model_id,
            "adapter_name": self.adapter_name,
            "timestamp": (
                self.timestamp.isoformat()
                if isinstance(self.timestamp, datetime)
                else self.timestamp
            ),
            "accuracy": self.accuracy,
            "scores": self.scores,
            "num_samples": self.num_samples,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "duration_seconds": self.duration_seconds,
            "metrics": self.metrics,
        }
