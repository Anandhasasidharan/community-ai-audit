from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import MechanisticInterpreter

log = logging.getLogger(__name__)


class LayerAnalysis(MechanisticInterpreter):
    name = "layer_analysis"
    description = "Analyzes model behavior across hypothetical transformer layers"
    version = "0.1.0"

    LAYER_PROBES = [
        {
            "input": "Define machine learning.",
            "layer_hints": ["early", "mid", "late"],
        },
        {
            "input": "Translate hello to French.",
            "layer_hints": ["early", "mid", "late"],
        },
        {
            "input": "Write a poem about nature.",
            "layer_hints": ["early", "mid", "late"],
        },
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.probes = cfg.get("probes", self.LAYER_PROBES)

    def analyze(
        self,
        model: Any,
        adapter: Any,
        inputs: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if config and "probes" in config:
            self.probes = config["probes"]

        probes = inputs or [p["input"] for p in self.probes]
        layer_insights: List[Dict[str, Any]] = []
        depth_estimates: List[float] = []

        for inp in probes:
            try:
                if hasattr(adapter, "generate"):
                    output = adapter.generate(model, inp)
                else:
                    output = str(adapter.predict(model, inp))
            except Exception as e:
                log.warning("Layer analysis probe failed: %s", e)
                output = ""

            depth = self._estimate_depth(inp, output)
            depth_estimates.append(depth)

            layer_insights.append(
                {
                    "input": inp[:80],
                    "output_preview": output[:150],
                    "estimated_depth": round(depth, 2),
                    "complexity_level": self._complexity_level(depth),
                }
            )

        avg_depth = sum(depth_estimates) / len(depth_estimates) if depth_estimates else 0.0
        score = max(0.0, min(100.0, avg_depth * 100.0))

        return {
            "interpreter_name": self.name,
            "score": round(score, 1),
            "total_probes": len(layer_insights),
            "avg_depth_estimate": round(avg_depth, 3),
            "layer_insights": layer_insights,
            "details": {
                "estimated_num_layers": None,
                "early_vs_late_ratio": round(self._early_vs_late(depth_estimates), 2),
                "complexity_distribution": self._complexity_distribution(depth_estimates),
            },
        }

    def _estimate_depth(self, inp: str, output: str) -> float:
        if not output:
            return 0.0
        input_len = len(inp.split())
        output_len = len(output.split())
        if output_len <= input_len:
            return 0.3
        if output_len > input_len * 3:
            return 0.9
        if output_len > input_len * 2:
            return 0.7
        return 0.5

    def _complexity_level(self, depth: float) -> str:
        if depth >= 0.8:
            return "deep"
        if depth >= 0.5:
            return "medium"
        return "shallow"

    def _early_vs_late(self, depths: List[float]) -> float:
        if not depths:
            return 1.0
        early = sum(1 for d in depths if d < 0.5)
        late = sum(1 for d in depths if d >= 0.5)
        return early / late if late > 0 else float("inf")

    def _complexity_distribution(self, depths: List[float]) -> Dict[str, int]:
        dist: Dict[str, int] = {"shallow": 0, "medium": 0, "deep": 0}
        for d in depths:
            level = self._complexity_level(d)
            dist[level] = dist.get(level, 0) + 1
        return dist
