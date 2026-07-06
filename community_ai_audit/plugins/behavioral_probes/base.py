from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BehavioralProbe(ABC):
    name: str = "base_behavioral_probe"
    description: str = ""
    version: str = "0.1.0"

    @abstractmethod
    def analyze(
        self,
        model: Any,
        adapter: Any,
        inputs: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run a black-box behavioral heuristic analysis.

        Does not access model internals (weights, activations, attention).
        Returns dict with at minimum:
            - interpreter_name: str
            - score: float (0-100)
            - details: dict of analysis-specific results
        """
        raise NotImplementedError
