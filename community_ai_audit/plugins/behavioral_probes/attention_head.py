from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import BehavioralProbe

log = logging.getLogger(__name__)


class AttentionHeadAnalysis(BehavioralProbe):
    name = "attention_head_analysis"
    description = "Black-box heuristic: measures input-output word overlap as a proxy for attention complexity. Does not access attention weights."
    version = "0.1.0"

    ATTENTION_PROBES = [
        "The cat sat on the mat.",
        "After the rain, the sun came out.",
        "The CEO of the company announced the merger.",
        "She handed him the book that he had been looking for.",
        "The results of the experiment were inconclusive.",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.probes = cfg.get("probes", self.ATTENTION_PROBES)

    def analyze(
        self,
        model: Any,
        adapter: Any,
        inputs: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if config and "probes" in config:
            self.probes = config["probes"]

        probes = inputs or self.probes
        probe_analyses: List[Dict[str, Any]] = []
        max_attention_span = 0

        for inp in probes:
            try:
                if hasattr(adapter, "generate"):
                    output = adapter.generate(model, inp)
                else:
                    output = str(adapter.predict(model, inp))
            except Exception as e:
                log.warning("Attention head probe failed: %s", e)
                output = ""

            complexity = self._estimate_attention_complexity(inp, output)
            probe_analyses.append(
                {
                    "input": inp[:80],
                    "output_preview": output[:150],
                    "estimated_complexity": round(complexity, 2),
                    "input_tokens": len(inp.split()),
                    "output_tokens": len(output.split()) if output else 0,
                }
            )
            if complexity > max_attention_span:
                max_attention_span = complexity

        avg_complexity = (
            sum(p["estimated_complexity"] for p in probe_analyses) / len(probe_analyses)
            if probe_analyses
            else 0.0
        )

        score = max(0.0, min(100.0, avg_complexity * 100.0))

        return {
            "interpreter_name": self.name,
            "score": round(score, 1),
            "total_probes": len(probe_analyses),
            "avg_complexity": round(avg_complexity, 3),
            "max_attention_span": round(max_attention_span, 2),
            "probe_analyses": probe_analyses,
            "details": {
                "method": "word_overlap_ratio",
                "avg_complexity": round(avg_complexity, 2),
            },
        }

    def _estimate_attention_complexity(self, inp: str, output: str) -> float:
        if not output:
            return 0.0
        if len(inp.split()) < 5:
            return 0.0
        output_words = output.split()
        input_words = inp.split()
        if len(output_words) < 3:
            return 0.1
        overlap = len(set(w.lower() for w in output_words) & set(w.lower() for w in input_words))
        ratio = overlap / len(input_words) if input_words else 0
        return min(1.0, ratio * 1.5)
