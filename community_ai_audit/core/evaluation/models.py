from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class EvaluationResult:
    """Result of a single evaluation run (scanners + policies + reliability)."""

    model_id: str
    adapter_name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    scan_results: List[Dict[str, Any]] = field(default_factory=list)
    policy_results: List[Dict[str, Any]] = field(default_factory=list)
    reliability_results: List[Dict[str, Any]] = field(default_factory=list)
    risk_scores: Optional[Dict[str, float]] = None
    session_id: str = ""

    @property
    def total_findings(self) -> int:
        return sum(len(r.get("findings", [])) for r in self.scan_results)

    @property
    def passed_policies(self) -> int:
        return sum(1 for r in self.policy_results if r.get("status") == "pass")

    @property
    def failed_policies(self) -> int:
        return sum(1 for r in self.policy_results if r.get("status") == "fail")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "model_id": self.model_id,
            "adapter_name": self.adapter_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "total_findings": self.total_findings,
            "passed_policies": self.passed_policies,
            "failed_policies": self.failed_policies,
            "scan_results": self.scan_results,
            "policy_results": self.policy_results,
            "reliability_results": self.reliability_results,
            "risk_scores": self.risk_scores,
        }


@dataclass
class BenchmarkResult:
    """Result of a benchmark run against a dataset."""

    benchmark_name: str
    dataset_name: str
    dataset_version: str
    model_id: str
    adapter_name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    num_samples: int = 0
    num_passed: int = 0
    num_failed: int = 0
    accuracy: float = 0.0
    scores: Dict[str, float] = field(default_factory=dict)
    per_sample_results: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        return self.num_passed / self.num_samples if self.num_samples > 0 else 0.0

    @property
    def fail_rate(self) -> float:
        return self.num_failed / self.num_samples if self.num_samples > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark_name": self.benchmark_name,
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "model_id": self.model_id,
            "adapter_name": self.adapter_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "num_samples": self.num_samples,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "accuracy": self.accuracy,
            "pass_rate": self.pass_rate,
            "fail_rate": self.fail_rate,
            "scores": self.scores,
            "metrics": self.metrics,
        }


@dataclass
class RegressionReport:
    """Report comparing two benchmark runs to detect regression."""

    baseline: BenchmarkResult
    current: BenchmarkResult
    metric_deltas: Dict[str, float] = field(default_factory=dict)
    regressions: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    threshold: float = 0.05

    @property
    def has_regression(self) -> bool:
        return len(self.regressions) > 0

    @property
    def has_improvement(self) -> bool:
        return len(self.improvements) > 0

    @property
    def accuracy_delta(self) -> float:
        return self.current.accuracy - self.baseline.accuracy

    def summary(self) -> str:
        parts = [
            f"Regression: {self.baseline.benchmark_name}",
            f"Accuracy: {self.baseline.accuracy:.3f} -> {self.current.accuracy:.3f} ({self.accuracy_delta:+.3f})",
        ]
        if self.regressions:
            parts.append(f"Regressions: {', '.join(self.regressions)}")
        if self.improvements:
            parts.append(f"Improvements: {', '.join(self.improvements)}")
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline": self.baseline.to_dict(),
            "current": self.current.to_dict(),
            "accuracy_delta": self.accuracy_delta,
            "metric_deltas": self.metric_deltas,
            "regressions": self.regressions,
            "improvements": self.improvements,
            "threshold": self.threshold,
            "has_regression": self.has_regression,
            "has_improvement": self.has_improvement,
        }
