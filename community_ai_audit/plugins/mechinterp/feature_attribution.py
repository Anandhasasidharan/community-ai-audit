from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from .base import MechanisticInterpreter

log = logging.getLogger(__name__)


class FeatureAttribution(MechanisticInterpreter):
    name = "feature_attribution"
    description = "Estimates which input features drive model outputs"
    version = "0.1.0"

    ATTRIBUTION_INPUTS = [
        "The movie was absolutely terrible and boring.",
        "The service was excellent and very fast.",
        "This product is okay but could be better.",
        "I love the new design, it works perfectly.",
        "The package arrived damaged and late.",
    ]

    SENTIMENT_WORDS = {
        "positive": [
            "excellent",
            "love",
            "great",
            "perfect",
            "amazing",
            "wonderful",
            "good",
            "fast",
            "beautiful",
        ],
        "negative": [
            "terrible",
            "boring",
            "damaged",
            "late",
            "awful",
            "horrible",
            "bad",
            "worst",
            "hate",
        ],
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.inputs = cfg.get("inputs", self.ATTRIBUTION_INPUTS)
        self.sentiment_words = cfg.get("sentiment_words", self.SENTIMENT_WORDS)

    def analyze(
        self,
        model: Any,
        adapter: Any,
        inputs: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if config:
            self.inputs = config.get("inputs", self.inputs)
            self.sentiment_words = config.get("sentiment_words", self.sentiment_words)

        probes = inputs or self.inputs
        attributions: List[Dict[str, Any]] = []
        total_features = 0
        attributed_features = 0

        for inp in probes:
            try:
                if hasattr(adapter, "generate"):
                    output = adapter.generate(model, inp)
                else:
                    output = str(adapter.predict(model, inp))
            except Exception as e:
                log.warning("Feature attribution probe failed: %s", e)
                output = ""

            feature_map = self._attribute_features(inp, output)
            total_features += feature_map.get("total_input_features", 1)
            attributed_features += feature_map.get("attributed_features", 0)

            attributions.append(
                {
                    "input": inp[:80],
                    "output_preview": output[:150],
                    "feature_map": feature_map,
                    "sentiment_matched": feature_map.get("sentiment_match", False),
                }
            )

        attribution_rate = attributed_features / total_features if total_features > 0 else 0.0
        score = max(0.0, min(100.0, attribution_rate * 100.0))

        return {
            "interpreter_name": self.name,
            "score": round(score, 1),
            "total_probes": len(attributions),
            "attribution_rate": round(attribution_rate, 3),
            "attributions": attributions,
            "details": {
                "total_features": total_features,
                "attributed_features": attributed_features,
                "feature_importance_available": True,
            },
        }

    def _attribute_features(self, inp: str, output: str) -> Dict[str, Any]:
        input_words = set(re.findall(r"\b[a-zA-Z]+\b", inp.lower()))
        output_words = set(re.findall(r"\b[a-zA-Z]+\b", output.lower())) if output else set()

        if not input_words:
            return {
                "total_input_features": 0,
                "attributed_features": 0,
                "feature_importance": {},
                "sentiment_match": False,
            }

        features = {}
        for word in input_words:
            importance = 1.0 if word in output_words else 0.0
            features[word] = round(importance, 2)
        attributed = sum(1 for v in features.values() if v > 0)

        input_sentiment = self._detect_sentiment(inp)
        output_sentiment = self._detect_sentiment(output) if output else "neutral"

        return {
            "total_input_features": len(features),
            "attributed_features": attributed,
            "feature_importance": features,
            "sentiment_match": input_sentiment == output_sentiment,
        }

    def _detect_sentiment(self, text: str) -> str:
        pos = sum(1 for w in self.sentiment_words["positive"] if w in text.lower())
        neg = sum(1 for w in self.sentiment_words["negative"] if w in text.lower())
        if pos > neg:
            return "positive"
        if neg > pos:
            return "negative"
        return "neutral"
