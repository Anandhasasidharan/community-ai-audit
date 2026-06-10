from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ReliabilityScanner(ABC):
    """Abstract base for reliability scanning plugins.

    Reliability scanners evaluate model trustworthiness along dimensions
    like hallucination rate, citation accuracy, output consistency,
    and confidence calibration.
    """

    name: str = "base_reliability"
    description: str = ""
    version: str = "0.1.0"

    @abstractmethod
    def scan(
        self,
        model: Any,
        adapter: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run a reliability check on the model.

        Args:
            model: The loaded model.
            adapter: The model adapter for generate/predict calls.
            config: Optional scanner-specific config.

        Returns:
            Dict with at minimum:
                - scanner_name: str
                - score: float (0-100)
                - details: dict of metric-specific results
        """
        raise NotImplementedError
