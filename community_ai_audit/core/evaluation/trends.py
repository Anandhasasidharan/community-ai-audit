from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class TrendSnapshot:
    model_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    snapshot_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "model_id": self.model_id,
            "timestamp": self.timestamp.isoformat(),
            "scores": self.scores,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrendSnapshot":
        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        return cls(
            model_id=data["model_id"],
            timestamp=ts,
            scores=data.get("scores", {}),
            metadata=data.get("metadata", {}),
            snapshot_id=data.get("snapshot_id", ""),
        )


@dataclass
class TrendResult:
    dimension: str
    direction: str
    magnitude: float
    slope: float
    current: float
    previous: float
    window: int
    values: List[float] = field(default_factory=list)

    @property
    def is_degrading(self) -> bool:
        return self.direction == "degrading"

    @property
    def is_improving(self) -> bool:
        return self.direction == "improving"

    @property
    def is_stable(self) -> bool:
        return self.direction == "stable"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "direction": self.direction,
            "magnitude": self.magnitude,
            "slope": self.slope,
            "current": self.current,
            "previous": self.previous,
            "window": self.window,
        }

    def summary(self) -> str:
        return (
            f"{self.dimension}: {self.direction} "
            f"(current={self.current:.1f}, prev={self.previous:.1f}, "
            f"slope={self.slope:+.3f}, mag={self.magnitude:.2f})"
        )


DEFAULT_TREND_STORAGE = "~/.community-ai-audit/trends"
TREND_DEGRADE_THRESHOLD = -5.0
TREND_IMPROVE_THRESHOLD = 5.0


class AuditTrendTracker:
    """Tracks audit scores across time for trend analysis across all 7 dimensions.

    Stores snapshots per model_id in JSONL files. Computes direction, slope,
    and magnitude over a configurable window.
    """

    def __init__(self, storage_dir: str = DEFAULT_TREND_STORAGE):
        self._storage_dir = Path(storage_dir).expanduser()
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def _model_path(self, model_id: str) -> Path:
        safe = model_id.replace("/", "_").replace(":", "_")
        return self._storage_dir / f"{safe}.jsonl"

    def record(
        self,
        model_id: str,
        scores: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        snapshot_id = f"{model_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        snapshot = TrendSnapshot(
            model_id=model_id,
            scores=scores,
            metadata=metadata or {},
            snapshot_id=snapshot_id,
        )
        path = self._model_path(model_id)
        with open(path, "a") as f:
            f.write(json.dumps(snapshot.to_dict()) + "\n")
        log.debug("Recorded trend snapshot %s for model %s", snapshot_id, model_id)
        return snapshot_id

    def get_history(
        self,
        model_id: str,
        dimension: Optional[str] = None,
        limit: int = 10,
    ) -> List[TrendSnapshot]:
        path = self._model_path(model_id)
        if not path.exists():
            return []
        snapshots: List[TrendSnapshot] = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    snapshots.append(TrendSnapshot.from_dict(json.loads(line)))
        snapshots.sort(key=lambda s: s.timestamp, reverse=True)
        if limit > 0:
            snapshots = snapshots[:limit]
        if dimension:
            snapshots = [s for s in snapshots if dimension in s.scores]
        return snapshots

    def get_latest(self, model_id: str) -> Optional[TrendSnapshot]:
        history = self.get_history(model_id, limit=1)
        return history[0] if history else None

    def compute_trend(
        self,
        model_id: str,
        dimension: str,
        window: int = 3,
    ) -> TrendResult:
        history = self.get_history(model_id, limit=window)
        if not history:
            return TrendResult(
                dimension=dimension,
                direction="insufficient_data",
                magnitude=0.0,
                slope=0.0,
                current=0.0,
                previous=0.0,
                window=window,
            )
        values = [s.scores.get(dimension, 0.0) for s in reversed(history)]
        if dimension not in history[0].scores:
            return TrendResult(
                dimension=dimension,
                direction="insufficient_data",
                magnitude=0.0,
                slope=0.0,
                current=0.0,
                previous=0.0,
                window=window,
            )
        current = values[-1] if values else 0.0
        previous = values[-2] if len(values) >= 2 else current
        if len(values) < 2:
            return TrendResult(
                dimension=dimension,
                direction="stable",
                magnitude=0.0,
                slope=0.0,
                current=current,
                previous=previous,
                window=window,
                values=values,
            )
        n = len(values)
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(values) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
        den = sum((x - mean_x) ** 2 for x in xs)
        slope = num / den if den != 0 else 0.0
        magnitude = slope * (n - 1)
        delta = current - values[0]
        if delta <= TREND_DEGRADE_THRESHOLD:
            direction = "degrading"
        elif delta >= TREND_IMPROVE_THRESHOLD:
            direction = "improving"
        else:
            direction = "stable"
        return TrendResult(
            dimension=dimension,
            direction=direction,
            magnitude=magnitude,
            slope=slope,
            current=current,
            previous=previous,
            window=window,
            values=values,
        )

    def list_models(self) -> List[str]:
        models = []
        for f in self._storage_dir.iterdir():
            if f.suffix == ".jsonl":
                models.append(f.stem)
        return sorted(models)

    def cleanup(self, max_snapshots: int = 100):
        for model_id in self.list_models():
            history = self.get_history(model_id, limit=0)
            if len(history) > max_snapshots:
                path = self._model_path(model_id)
                keep = history[:max_snapshots]
                keep.reverse()
                with open(path, "w") as f:
                    for s in keep:
                        f.write(json.dumps(s.to_dict()) + "\n")
                log.info("Cleaned %s snapshots for %s", len(history) - max_snapshots, model_id)

    def trend_report(
        self,
        model_id: str,
        dimensions: Optional[List[str]] = None,
        window: int = 3,
    ) -> Dict[str, TrendResult]:
        if dimensions is None:
            dimensions = [
                "security", "reliability", "compliance", "agent_risk",
                "alignment", "red_team", "interpretability",
            ]
        results = {}
        for dim in dimensions:
            results[dim] = self.compute_trend(model_id, dim, window=window)
        return results
