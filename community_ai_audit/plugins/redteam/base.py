from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AttackResult:
    attack_type: str
    prompt: str
    success: bool
    output_preview: str = ""
    risk_score: float = 0.0
    evidence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attack_type": self.attack_type,
            "prompt": self.prompt[:200],
            "success": self.success,
            "output_preview": self.output_preview[:200],
            "risk_score": round(self.risk_score, 2),
            "evidence": self.evidence,
            "metadata": self.metadata,
        }


class AttackGenerator(ABC):
    name: str = "base_attack_generator"
    description: str = ""

    @abstractmethod
    def generate(self, config: Optional[Dict[str, Any]] = None) -> List[str]:
        """Generate attack prompts."""
        raise NotImplementedError


class AttackEvaluator(ABC):
    name: str = "base_attack_evaluator"
    description: str = ""

    @abstractmethod
    def evaluate(self, prompt: str, output: str) -> bool:
        """Determine if the attack was successful."""
        raise NotImplementedError
