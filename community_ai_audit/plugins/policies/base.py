from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class PolicyPlugin(ABC):
    """Abstract base for policy testing plugins.

    A policy defines a rule that model outputs must satisfy.
    Policies produce pass/fail results with evidence and confidence.
    """

    name: str = "base_policy"
    description: str = ""
    category: str = "general"
    version: str = "0.1.0"

    @abstractmethod
    def check(
        self,
        prompt: str,
        output: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Check whether a model response satisfies this policy.

        Args:
            prompt: The input prompt sent to the model.
            output: The model's response text.
            config: Optional policy-specific configuration.

        Returns:
            Dict with keys:
                - status: "pass" or "fail"
                - confidence: float 0.0-1.0
                - evidence: list of evidence strings
                - details: optional dict with extra info
        """
        raise NotImplementedError

    def get_config_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}
