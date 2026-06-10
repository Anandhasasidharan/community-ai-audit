from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import AlignmentScanner
from .sycophancy import SycophancyScanner
from .preference_drift import PreferenceDriftScanner
from .value_alignment import ValueAlignmentScanner
from .objective_robustness import ObjectiveRobustnessScanner

log = logging.getLogger(__name__)

_BUILTIN_ALIGNMENT: Dict[str, type] = {
    SycophancyScanner.name: SycophancyScanner,
    PreferenceDriftScanner.name: PreferenceDriftScanner,
    ValueAlignmentScanner.name: ValueAlignmentScanner,
    ObjectiveRobustnessScanner.name: ObjectiveRobustnessScanner,
}


def _norm(name: str) -> str:
    return name.lower().replace("_", "-")


def list_alignment_scanners() -> List[str]:
    return sorted(_BUILTIN_ALIGNMENT.keys())


def get_alignment_scanner(name: str, config: Optional[Dict[str, Any]] = None) -> AlignmentScanner:
    norm = _norm(name)
    for key, cls in _BUILTIN_ALIGNMENT.items():
        if _norm(key) == norm:
            return cls(config=config) if config is not None else cls()
    raise KeyError(
        f"Alignment scanner '{name}' not found. Available: {list(_BUILTIN_ALIGNMENT.keys())}"
    )


def run_alignment_scanners(
    scanners: Optional[List[str]] = None,
    model=None,
    adapter=None,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if scanners is None:
        scanners = list_alignment_scanners()

    results: List[Dict[str, Any]] = []

    for name in scanners:
        try:
            scanner = get_alignment_scanner(name, config=config)
            result = scanner.evaluate(model, adapter, config=config)
            results.append(result)
            log.info(
                "Alignment scanner '%s': score=%.1f confidence=%.2f",
                name,
                result.get("score", 0),
                result.get("confidence", 0),
            )
        except KeyError:
            log.warning("Alignment scanner '%s' not found, skipping", name)
        except Exception as e:
            log.error("Alignment scanner '%s' failed: %s", name, e)
            results.append(
                {
                    "scanner_name": name,
                    "score": 0.0,
                    "alignment_score": 0.0,
                    "confidence": 0.0,
                    "error": str(e),
                }
            )

    return results


__all__ = [
    "AlignmentScanner",
    "SycophancyScanner",
    "PreferenceDriftScanner",
    "ValueAlignmentScanner",
    "ObjectiveRobustnessScanner",
    "list_alignment_scanners",
    "get_alignment_scanner",
    "run_alignment_scanners",
]
