from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class RiskScore:
    """Container for all risk scores produced by the scoring engine."""

    security_score: float = 0.0
    reliability_score: float = 0.0
    compliance_score: float = 0.0
    agent_risk_score: float = 100.0
    alignment_score: float = 100.0
    red_team_score: float = 100.0
    interpretability_score: float = 0.0
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

    score_components: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "security_score": round(self.security_score, 1),
            "reliability_score": round(self.reliability_score, 1),
            "compliance_score": round(self.compliance_score, 1),
            "agent_risk_score": round(self.agent_risk_score, 1),
            "alignment_score": round(self.alignment_score, 1),
            "red_team_score": round(self.red_team_score, 1),
            "interpretability_score": round(self.interpretability_score, 1),
            "overall_score": round(self.overall_score, 1),
            "weights": self.weights,
        }

    @property
    def max_score(self) -> float:
        return max(
            self.security_score,
            self.reliability_score,
            self.compliance_score,
            self.agent_risk_score,
            self.alignment_score,
            self.red_team_score,
        )

    @property
    def min_score(self) -> float:
        return min(
            self.security_score,
            self.reliability_score,
            self.compliance_score,
            self.agent_risk_score,
            self.alignment_score,
            self.red_team_score,
        )

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
            f"Security: {self.security_score:.1f}",
            f"Reliability: {self.reliability_score:.1f}",
            f"Compliance: {self.compliance_score:.1f}",
            f"Agent Risk: {self.agent_risk_score:.1f}",
            f"Alignment: {self.alignment_score:.1f}",
            f"Red Team: {self.red_team_score:.1f}",
            f"Interpretability: {self.interpretability_score:.1f}",
        ]
        return " | ".join(parts)


@dataclass
class OverallAuditScore:
    security: float = 0.0
    reliability: float = 0.0
    compliance: float = 0.0
    agent_risk: float = 100.0
    alignment: float = 100.0
    red_team: float = 100.0
    interpretability: float = 0.0
    overall: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "security": round(self.security, 1),
            "reliability": round(self.reliability, 1),
            "compliance": round(self.compliance, 1),
            "agent_risk": round(self.agent_risk, 1),
            "alignment": round(self.alignment, 1),
            "red_team": round(self.red_team, 1),
            "interpretability": round(self.interpretability, 1),
            "overall": round(self.overall, 1),
        }

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
