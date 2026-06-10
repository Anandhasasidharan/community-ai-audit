from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import MechanisticInterpreter
from .activation_probes import ActivationProbes
from .representation import RepresentationAnalysis
from .attention_head import AttentionHeadAnalysis
from .feature_attribution import FeatureAttribution
from .layer_analysis import LayerAnalysis

log = logging.getLogger(__name__)

_BUILTIN_MECHINTERP: Dict[str, type] = {
    ActivationProbes.name: ActivationProbes,
    RepresentationAnalysis.name: RepresentationAnalysis,
    AttentionHeadAnalysis.name: AttentionHeadAnalysis,
    FeatureAttribution.name: FeatureAttribution,
    LayerAnalysis.name: LayerAnalysis,
}


def _norm(name: str) -> str:
    return name.lower().replace("_", "-")


def list_mechinterp_analyzers() -> List[str]:
    return sorted(_BUILTIN_MECHINTERP.keys())


def get_mechinterp_analyzer(
    name: str, config: Optional[Dict[str, Any]] = None
) -> MechanisticInterpreter:
    norm = _norm(name)
    for key, cls in _BUILTIN_MECHINTERP.items():
        if _norm(key) == norm:
            return cls(config=config) if config is not None else cls()
    raise KeyError(
        f"Mechanistic interpreter '{name}' not found. Available: {list(_BUILTIN_MECHINTERP.keys())}"
    )


def run_mechinterp_analyzers(
    analyzers: Optional[List[str]] = None,
    model=None,
    adapter=None,
    inputs: Optional[List[str]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if analyzers is None:
        analyzers = list_mechinterp_analyzers()

    results: List[Dict[str, Any]] = []

    for name in analyzers:
        try:
            analyzer = get_mechinterp_analyzer(name, config=config)
            result = analyzer.analyze(model, adapter, inputs=inputs, config=config)
            results.append(result)
            log.info(
                "Mechanistic interpreter '%s': score=%.1f",
                name,
                result.get("score", 0),
            )
        except KeyError:
            log.warning("Mechanistic interpreter '%s' not found, skipping", name)
        except Exception as e:
            log.error("Mechanistic interpreter '%s' failed: %s", name, e)
            results.append(
                {
                    "interpreter_name": name,
                    "score": 0.0,
                    "error": str(e),
                }
            )

    return results


__all__ = [
    "MechanisticInterpreter",
    "ActivationProbes",
    "RepresentationAnalysis",
    "AttentionHeadAnalysis",
    "FeatureAttribution",
    "LayerAnalysis",
    "list_mechinterp_analyzers",
    "get_mechinterp_analyzer",
    "run_mechinterp_analyzers",
]
