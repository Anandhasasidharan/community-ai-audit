from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DriftReport:
    scanner_name: str
    baseline_score: float
    current_score: float
    delta: float
    drifted: bool
    threshold: float
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scanner_name": self.scanner_name,
            "baseline_score": self.baseline_score,
            "current_score": self.current_score,
            "delta": round(self.delta, 2),
            "drifted": self.drifted,
            "threshold": self.threshold,
            "details": self.details,
        }


class DriftDetector:
    """Detects drift in agent audit scores over time.

    Compares recent audit results to a baseline window
    to identify statistically significant changes.
    """

    def __init__(self, threshold: float = 10.0):
        self.threshold = threshold

    def detect_drift(
        self,
        baseline_records: List[Dict[str, Any]],
        current_records: List[Dict[str, Any]],
    ) -> List[DriftReport]:
        """Compare baseline audit records to current records.

        Args:
            baseline_records: Historical audit records (the baseline).
            current_records: Recent audit records to check against.

        Returns:
            List of DriftReport per scanner.
        """
        baseline_scores = self._aggregate_scores(baseline_records)
        current_scores = self._aggregate_scores(current_records)
        all_scanners = set(baseline_scores.keys()) | set(current_scores.keys())

        reports: List[DriftReport] = []
        for scanner in sorted(all_scanners):
            base_val = baseline_scores.get(scanner, 0.0)
            cur_val = current_scores.get(scanner, 0.0)
            delta = cur_val - base_val
            drifted = abs(delta) > self.threshold
            reports.append(
                DriftReport(
                    scanner_name=scanner,
                    baseline_score=round(base_val, 1),
                    current_score=round(cur_val, 1),
                    delta=delta,
                    drifted=drifted,
                    threshold=self.threshold,
                    details={
                        "baseline_count": len(baseline_records),
                        "current_count": len(current_records),
                        "direction": self._direction(delta),
                    },
                )
            )
        return reports

    def _aggregate_scores(
        self, records: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        scanner_scores: Dict[str, List[float]] = {}
        for record in records:
            for result in record.get("scanner_results", []):
                name = result.get("scanner_name", "")
                score = result.get("score", 0.0)
                scanner_scores.setdefault(name, []).append(score)

        return {
            name: sum(scores) / len(scores)
            for name, scores in scanner_scores.items()
        }

    def _direction(self, delta: float) -> str:
        if delta > self.threshold:
            return "improvement"
        if delta < -self.threshold:
            return "degradation"
        return "stable"
