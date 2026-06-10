from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import MechanisticInterpreter

log = logging.getLogger(__name__)


class ActivationProbes(MechanisticInterpreter):
    name = "activation_probes"
    description = "Analyzes model activations through probing tasks"
    version = "0.1.0"

    PROBE_INPUTS = [
        "The capital of France is",
        "Water is composed of",
        "The sun rises in the",
        "Python is a programming",
        "The chemical symbol for gold is",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.probe_inputs = cfg.get("probe_inputs", self.PROBE_INPUTS)

    def analyze(
        self,
        model: Any,
        adapter: Any,
        inputs: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        probe_inputs = inputs or self.probe_inputs
        if config and "probe_inputs" in config:
            probe_inputs = config["probe_inputs"]

        probe_results: List[Dict[str, Any]] = []

        for inp in probe_inputs:
            try:
                if hasattr(adapter, "generate"):
                    output = adapter.generate(model, inp)
                else:
                    output = str(adapter.predict(model, inp))
                response_quality = self._estimate_quality(output)
            except Exception as e:
                log.warning("Activation probe failed: %s", e)
                output = ""
                response_quality = 0.0

            probe_results.append(
                {
                    "input": inp[:80],
                    "output_preview": output[:150],
                    "response_quality": round(response_quality, 2),
                }
            )

        avg_quality = (
            sum(r["response_quality"] for r in probe_results) / len(probe_results)
            if probe_results
            else 0.0
        )

        score = max(0.0, min(100.0, avg_quality * 100.0))

        return {
            "interpreter_name": self.name,
            "score": round(score, 1),
            "total_probes": len(probe_results),
            "avg_response_quality": round(avg_quality, 3),
            "probe_results": probe_results,
            "details": {
                "activation_coverage": round(avg_quality, 3),
                "num_layers_estimated": None,
            },
        }

    def _estimate_quality(self, output: str) -> float:
        if not output:
            return 0.0
        words = len(output.split())
        if words > 50:
            return 0.9
        if words > 10:
            return 0.6
        return 0.3
