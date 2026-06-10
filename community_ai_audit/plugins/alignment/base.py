from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class AlignmentScanner(ABC):
    name: str = "base_alignment"
    description: str = ""
    version: str = "0.1.0"

    @abstractmethod
    def evaluate(
        self,
        model: Any,
        adapter: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run an alignment evaluation on the model.

        Returns dict with at minimum:
            - scanner_name: str
            - score: float (0-100, higher = more aligned)
            - alignment_score: float (0-100)
            - confidence: float (0-1)
            - evidence: list of dicts
            - details: dict
        """
        raise NotImplementedError
