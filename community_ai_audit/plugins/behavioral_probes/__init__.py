from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import BehavioralProbe
from .activation_probes import ActivationProbes
from .representation import RepresentationAnalysis
from .attention_head import AttentionHeadAnalysis
from .feature_attribution import FeatureAttribution
from .layer_analysis import LayerAnalysis

log = logging.getLogger(__name__)

_BUILTIN_PROBES: Dict[str, type] = {
    ActivationProbes.name: ActivationProbes,
    RepresentationAnalysis.name: RepresentationAnalysis,
    AttentionHeadAnalysis.name: AttentionHeadAnalysis,
    FeatureAttribution.name: FeatureAttribution,
    LayerAnalysis.name: LayerAnalysis,
}


def _norm(name: str) -> str:
    return name.lower().replace("_", "-")


def list_behavioral_probes() -> List[str]:
    return sorted(_BUILTIN_PROBES.keys())


def get_behavioral_probe(
    name: str, config: Optional[Dict[str, Any]] = None
) -> BehavioralProbe:
    norm = _norm(name)
    for key, cls in _BUILTIN_PROBES.items():
        if _norm(key) == norm:
            return cls(config=config) if config is not None else cls()
    raise KeyError(
        f"Behavioral probe '{name}' not found. Available: {list(_BUILTIN_PROBES.keys())}"
    )


def run_behavioral_probes(
    analyzers: Optional[List[str]] = None,
    model=None,
    adapter=None,
    inputs: Optional[List[str]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if analyzers is None:
        analyzers = list_behavioral_probes()

    results: List[Dict[str, Any]] = []

    for name in analyzers:
        try:
            analyzer = get_behavioral_probe(name, config=config)
            result = analyzer.analyze(model, adapter, inputs=inputs, config=config)
            results.append(result)
            log.info(
                "Behavioral probe '%s': score=%.1f",
                name,
                result.get("score", 0),
            )
        except KeyError:
            log.warning("Behavioral probe '%s' not found, skipping", name)
        except Exception as e:
            log.error("Behavioral probe '%s' failed: %s", name, e)
            results.append(
                {
                    "interpreter_name": name,
                    "score": 0.0,
                    "error": str(e),
                }
            )

    return results


__all__ = [
    "BehavioralProbe",
    "ActivationProbes",
    "RepresentationAnalysis",
    "AttentionHeadAnalysis",
    "FeatureAttribution",
    "LayerAnalysis",
    "list_behavioral_probes",
    "get_behavioral_probe",
    "run_behavioral_probes",
]
