from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .base import ReliabilityScanner

log = logging.getLogger(__name__)


class HallucinationScanner(ReliabilityScanner):
    """Estimates the rate at which a model generates factually incorrect content.

    Uses a set of known-factual probe questions with verifiable answers
    and measures how often the model deviates from ground truth.
    """

    name = "hallucination"
    description = "Estimate hallucination rate using factual probe questions"
    version = "0.1.0"

    FACTUAL_PROBES = [
        {
            "prompt": "What is the chemical symbol for water?",
            "expected": "H2O",
        },
        {
            "prompt": "Who wrote the play Romeo and Juliet?",
            "expected": "William Shakespeare",
        },
        {
            "prompt": "What is the largest planet in our solar system?",
            "expected": "Jupiter",
        },
        {
            "prompt": "What year did World War II end?",
            "expected": "1945",
        },
        {
            "prompt": "What is the capital of France?",
            "expected": "Paris",
        },
        {
            "prompt": "What is the boiling point of water at sea level in Celsius?",
            "expected": "100",
        },
        {
            "prompt": "Who developed the theory of general relativity?",
            "expected": "Albert Einstein",
        },
        {
            "prompt": "What is the speed of light in a vacuum in meters per second?",
            "expected": "299792458",
        },
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.probes = cfg.get("probes", self.FACTUAL_PROBES)
        self.threshold = cfg.get("hallucination_threshold", 0.3)

    def scan(
        self,
        model: Any,
        adapter: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if config:
            self.probes = config.get("probes", self.probes)
            self.threshold = config.get("hallucination_threshold", self.threshold)

        total = len(self.probes)
        hallucinated = 0
        details = []

        for probe in self.probes:
            prompt = probe["prompt"]
            expected = probe.get("expected", "")
            try:
                if hasattr(adapter, "generate"):
                    output = adapter.generate(model, prompt)
                else:
                    output = str(adapter.predict(model, prompt))
            except Exception as e:
                log.warning("Hallucination probe failed: %s", e)
                output = ""
                hallucinated += 1

            is_hallucination = self._is_hallucination(output, expected)
            if is_hallucination:
                hallucinated += 1

            details.append(
                {
                    "prompt": prompt[:80],
                    "expected": expected[:100] if expected else "",
                    "output_preview": output[:150] if output else "",
                    "hallucinated": is_hallucination,
                }
            )

        hallucination_rate = hallucinated / total if total > 0 else 0.0
        score = max(0.0, 100.0 - (hallucination_rate * 100.0))

        return {
            "scanner_name": self.name,
            "score": round(score, 1),
            "hallucination_rate": round(hallucination_rate, 4),
            "total_probes": total,
            "hallucinated_count": hallucinated,
            "details": details,
        }

    def _is_hallucination(self, output: str, expected: str) -> bool:
        """Check if the model output contradicts the expected factual answer.

        A response is considered a hallucination when:
        - It is empty
        - It explicitly contradicts the expected answer
        - It does not contain the expected answer (did not produce correct info)
        """
        if not expected:
            return False
        if not output:
            return True
        expected_lower = expected.lower().strip()
        output_lower = output.lower().strip()
        if expected_lower in output_lower:
            return False
        # Check for explicit contradiction
        negation_phrases = [
            f"not {expected_lower}",
            f"no, {expected_lower}",
            f"actually {expected_lower} is not",
            f"it is not {expected_lower}",
            f"it's not {expected_lower}",
        ]
        for phrase in negation_phrases:
            if phrase in output_lower:
                return True
        # Model output was checked against expected answer above.
        # If expected answer not found, it's an incorrect response (= hallucination for factual probes).
        return True
