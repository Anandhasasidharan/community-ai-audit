from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RiskScore:
    """Container for all risk scores produced by the scoring engine."""

    security_score: Optional[float] = None
    reliability_score: Optional[float] = None
    compliance_score: Optional[float] = None
    agent_risk_score: Optional[float] = None
    alignment_score: Optional[float] = None
    red_team_score: Optional[float] = None
    interpretability_score: Optional[float] = None
    overall_score: float = 0.0
    weights: Dict[str, float] = field(
        default_factory=lambda: {
            "security": 0.2,
            "reliability": 0.1,
            "compliance": 0.1,
            "agent_risk": 0.2,
            "alignment": 0.2,
            "red_team": 0.1,
            "interpretability": 0.1,
        }
    )

    coverage: List[str] = field(default_factory=list)
    score_components: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "overall_score": round(self.overall_score, 1),
            "coverage": self.coverage,
            "weights": self.weights,
        }
        for key in (
            "security",
            "reliability",
            "compliance",
            "agent_risk",
            "alignment",
            "red_team",
            "interpretability",
        ):
            val = getattr(self, f"{key}_score")
            d[f"{key}_score"] = round(val, 1) if val is not None else None
        return d

    @property
    def max_score(self) -> Optional[float]:
        scores = [
            s
            for s in [
                self.security_score,
                self.reliability_score,
                self.compliance_score,
                self.agent_risk_score,
                self.alignment_score,
                self.red_team_score,
            ]
            if s is not None
        ]
        return max(scores) if scores else None

    @property
    def min_score(self) -> Optional[float]:
        scores = [
            s
            for s in [
                self.security_score,
                self.reliability_score,
                self.compliance_score,
                self.agent_risk_score,
                self.alignment_score,
                self.red_team_score,
            ]
            if s is not None
        ]
        return min(scores) if scores else None

    def interpret_overall(self) -> str:
        if self.overall_score >= 90:
            return "Excellent"
        if self.overall_score >= 80:
            return "Good"
        if self.overall_score >= 70:
            return "Fair"
        if self.overall_score >= 60:
            return "Poor"
        return "Critical"

    def audit_summary(self) -> str:
        parts = [
            f"Overall: {self.overall_score:.1f} ({self.interpret_overall()})",
            f"Coverage: {', '.join(self.coverage) if self.coverage else 'none'}",
        ]
        for key in (
            "security",
            "reliability",
            "compliance",
            "agent_risk",
            "alignment",
            "red_team",
            "interpretability",
        ):
            val = getattr(self, f"{key}_score")
            parts.append(
                f"{key.replace('_', ' ').title()}: {val:.1f}"
                if val is not None
                else f"{key.replace('_', ' ').title()}: N/A"
            )
        return " | ".join(parts)


@dataclass
class OverallAuditScore:
    security: Optional[float] = None
    reliability: Optional[float] = None
    compliance: Optional[float] = None
    agent_risk: Optional[float] = None
    alignment: Optional[float] = None
    red_team: Optional[float] = None
    interpretability: Optional[float] = None
    overall: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"overall": round(self.overall, 1)}
        for key in (
            "security",
            "reliability",
            "compliance",
            "agent_risk",
            "alignment",
            "red_team",
            "interpretability",
        ):
            val = getattr(self, key)
            d[key] = round(val, 1) if val is not None else None
        return d

    def interpret(self) -> str:
        if self.overall >= 90:
            return "Excellent"
        if self.overall >= 80:
            return "Good"
        if self.overall >= 70:
            return "Fair"
        if self.overall >= 60:
            return "Poor"
        return "Critical"


DEFAULT_WEIGHTS: Dict[str, float] = {
    "security": 0.2,
    "reliability": 0.1,
    "compliance": 0.1,
    "agent_risk": 0.2,
    "alignment": 0.2,
    "red_team": 0.1,
    "interpretability": 0.1,
}
