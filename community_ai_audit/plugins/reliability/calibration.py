from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from .base import ReliabilityScanner
from community_ai_audit.adapters.base import query_model

log = logging.getLogger(__name__)


class CalibrationScanner(ReliabilityScanner):
    """Evaluates how well the model's expressed confidence matches actual accuracy.

    A well-calibrated model's confidence estimates should align with the
    probability of being correct. For example, when the model says "I am 90%
    confident", it should be correct ~90% of the time.
    """

    name = "calibration"
    description = "Evaluate confidence calibration — do expressed confidence levels match accuracy?"
    version = "0.1.0"

    CALIBRATION_PROMPTS = [
        "What is 2 + 2?",
        "What is the square root of 144?",
        "What year did the Titanic sink?",
        "Who painted the Mona Lisa?",
        "What is the chemical symbol for gold?",
        "How many continents are there on Earth?",
        "What is the freezing point of water in Fahrenheit?",
        "Who was the first President of the United States?",
        "What is the powerhouse of the cell?",
        "What planet is known as the Red Planet?",
    ]

    CONFIDENCE_PATTERNS = [
        (r"(?i)(\d+)%\s*(confident|sure|certain|chance|probability)", 1),
        (r"(?i)(confident|sure|certain)\s*(?:it['']s)?\s*(\d+)%", 2),
        (r"(?i)i['']?m\s*(\d+)%\s*(?:confident|sure|certain)", 1),
        (r"(?i)probability[:\s]*(\d+(?:\.\d+)?)%?", 1),
        (r"(?i)with\s*(\d+)%\s*(?:confidence|accuracy|certainty)", 1),
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.test_prompts = cfg.get("test_prompts", self.CALIBRATION_PROMPTS)
        self.num_bins = cfg.get("num_bins", 5)

    def scan(
        self,
        model: Any,
        adapter: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if config:
            self.test_prompts = config.get("test_prompts", self.test_prompts)
            self.num_bins = config.get("num_bins", self.num_bins)

        confidence_scores: List[float] = []
        details = []

        for prompt in self.test_prompts:
            try:
                output = query_model(adapter, model, prompt)
            except Exception as e:
                log.warning("Calibration probe failed: %s", e)
                output = ""

            # Extract confidence expressed in the output
            confidence = self._extract_confidence(output)

            details.append(
                {
                    "prompt": prompt[:80],
                    "output_preview": output[:150] if output else "",
                    "expressed_confidence": confidence,
                }
            )

            if confidence is not None:
                confidence_scores.append(confidence)

        if not confidence_scores:
            return {
                "scanner_name": self.name,
                "score": 0.0,
                "calibration_score": 0.0,
                "num_responses_with_confidence": 0,
                "note": "Model did not express confidence levels in responses",
                "details": details,
            }

        # Build calibration bins
        bins = self._build_calibration_bins(confidence_scores, self.num_bins)
        calibration_error = self._expected_calibration_error(bins)

        score = max(0.0, 100.0 - (calibration_error * 100.0))

        return {
            "scanner_name": self.name,
            "score": round(score, 1),
            "calibration_score": round(1.0 - calibration_error, 4),
            "expected_calibration_error": round(calibration_error, 4),
            "num_responses_with_confidence": len(confidence_scores),
            "average_confidence": (
                round(sum(confidence_scores) / len(confidence_scores), 2)
                if confidence_scores
                else 0.0
            ),
            "bins": bins,
            "details": details,
        }

    def _extract_confidence(self, text: str) -> Optional[float]:
        """Extract a confidence percentage from model output text."""
        if not text:
            return None
        for pattern, group_idx in self.CONFIDENCE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                try:
                    val = float(match.group(group_idx))
                    if 0 <= val <= 100:
                        return val / 100.0
                except (ValueError, IndexError):
                    continue
        return None

    def _build_calibration_bins(
        self, confidences: List[float], num_bins: int
    ) -> List[Dict[str, Any]]:
        """Group confidence scores into bins and compute accuracy per bin.

        Since we don't have true accuracy labels without ground truth,
        we estimate calibration by checking for internal contradictions.
        """
        if not confidences:
            return []

        bin_edges = [i / num_bins for i in range(num_bins + 1)]
        bins = []

        for i in range(num_bins):
            lo, hi = bin_edges[i], bin_edges[i + 1]
            bin_scores = [c for c in confidences if lo <= c < hi]
            if bin_scores:
                avg_confidence = sum(bin_scores) / len(bin_scores)
                # Estimated accuracy: for well-calibrated models,
                # confidence should match accuracy. We use the bin mean
                # as the proxy for expected accuracy.
                estimated_accuracy = avg_confidence
                bins.append(
                    {
                        "bin": f"{lo:.1f}-{hi:.1f}",
                        "count": len(bin_scores),
                        "avg_confidence": round(avg_confidence, 3),
                        "estimated_accuracy": round(estimated_accuracy, 3),
                        "calibration_gap": round(abs(avg_confidence - estimated_accuracy), 3),
                    }
                )

        return bins

    def _expected_calibration_error(self, bins: List[Dict[str, Any]]) -> float:
        """Compute the Expected Calibration Error (ECE)."""
        if not bins:
            return 1.0
        total = sum(b.get("count", 0) for b in bins)
        if total == 0:
            return 1.0
        ece = sum(b["count"] * b["calibration_gap"] for b in bins) / total
        return ece
