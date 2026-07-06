from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import BehavioralProbe

log = logging.getLogger(__name__)


class RepresentationAnalysis(BehavioralProbe):
    name = "representation_analysis"
    description = "Black-box heuristic: measures output similarity between paired probes (e.g. dog/cat, quantum/classical). Does not access internal representations."
    version = "0.1.0"

    REPRESENTATION_PROBES = [
        "Describe a dog.",
        "Describe a cat.",
        "What is happiness?",
        "What is sadness?",
        "Explain quantum physics.",
        "Explain classical mechanics.",
        "Write about democracy.",
        "Write about authoritarianism.",
    ]

    PAIRED_PROBES = [
        ("Describe a dog.", "Describe a cat."),
        ("What is happiness?", "What is sadness?"),
        ("Explain quantum physics.", "Explain classical mechanics."),
        ("Write about democracy.", "Write about authoritarianism."),
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.probes = cfg.get("probes", self.REPRESENTATION_PROBES)
        self.paired_probes = cfg.get("paired_probes", self.PAIRED_PROBES)

    def analyze(
        self,
        model: Any,
        adapter: Any,
        inputs: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if config:
            self.probes = config.get("probes", self.probes)
            self.paired_probes = config.get("paired_probes", self.paired_probes)

        probes = inputs or self.probes
        responses: List[Dict[str, Any]] = []
        response_lengths: List[int] = []

        for inp in probes:
            try:
                if hasattr(adapter, "generate"):
                    output = adapter.generate(model, inp)
                else:
                    output = str(adapter.predict(model, inp))
            except Exception as e:
                log.warning("Representation probe failed: %s", e)
                output = ""

            responses.append(
                {"input": inp[:80], "output_preview": output[:150], "length": len(output)}
            )
            response_lengths.append(len(output))

        pairwise: List[Dict[str, Any]] = []
        for a, b in self.paired_probes:
            resp_a = next((r["output_preview"] for r in responses if r["input"] == a[:80]), "")
            resp_b = next((r["output_preview"] for r in responses if r["input"] == b[:80]), "")
            differentiation = self._estimate_differentiation(resp_a, resp_b)
            pairwise.append(
                {
                    "concept_a": a[:60],
                    "concept_b": b[:60],
                    "differentiation_score": round(differentiation, 2),
                }
            )

        avg_diff = (
            sum(p["differentiation_score"] for p in pairwise) / len(pairwise) if pairwise else 0.0
        )

        score = max(0.0, min(100.0, avg_diff * 100.0))

        return {
            "interpreter_name": self.name,
            "score": round(score, 1),
            "total_probes": len(responses),
            "avg_response_length": (
                sum(response_lengths) / len(response_lengths) if response_lengths else 0
            ),
            "responses": responses,
            "pairwise_differentiation": pairwise,
            "details": {
                "avg_pairwise_diff": round(avg_diff, 3),
                "vocabulary_estimate": self._estimate_vocabulary(responses),
            },
        }

    def _estimate_differentiation(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a and not set_b:
            return 0.0
        jaccard = len(set_a & set_b) / len(set_a | set_b) if set_a | set_b else 1.0
        return 1.0 - jaccard

    def _estimate_vocabulary(self, responses: List[Dict[str, Any]]) -> int:
        all_words: set = set()
        for r in responses:
            for word in r.get("output_preview", "").split():
                all_words.add(word.lower().strip(".,!?;:"))
        return len(all_words)
