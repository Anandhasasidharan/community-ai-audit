from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import ReliabilityScanner
from .hallucination import HallucinationScanner
from .citation import CitationScanner
from .consistency import ConsistencyScanner
from .calibration import CalibrationScanner

log = logging.getLogger(__name__)

_BUILTIN_RELIABILITY: Dict[str, type] = {
    HallucinationScanner.name: HallucinationScanner,
    CitationScanner.name: CitationScanner,
    ConsistencyScanner.name: ConsistencyScanner,
    CalibrationScanner.name: CalibrationScanner,
}


def list_reliability_scanners() -> List[str]:
    return sorted(_BUILTIN_RELIABILITY.keys())


def get_reliability_scanner(
    name: str, config: Optional[Dict[str, Any]] = None
) -> ReliabilityScanner:
    norm = name.lower().replace("_", "-")
    for key, cls in _BUILTIN_RELIABILITY.items():
        if key.lower() == norm:
            return cls(config=config) if config is not None else cls()
    raise KeyError(
        f"Reliability scanner '{name}' not found. Available: {list(_BUILTIN_RELIABILITY.keys())}"
    )


def run_reliability_checks(
    checks: Optional[List[str]] = None,
    model=None,
    adapter=None,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Run a list of reliability scanners and return results.

    Args:
        checks: Scanner names to run. None = all.
        model: The loaded model.
        adapter: The model adapter.
        config: Optional config dict passed to each scanner.

    Returns:
        List of scanner result dicts.
    """
    if checks is None:
        checks = list_reliability_scanners()

    results: List[Dict[str, Any]] = []

    for name in checks:
        try:
            scanner = get_reliability_scanner(name, config=config)
            result = scanner.scan(model, adapter, config=config)
            results.append(result)
            log.info("Reliability scanner '%s' completed: score=%.1f", name, result.get("score", 0))
        except KeyError:
            log.warning("Reliability scanner '%s' not found, skipping", name)
        except Exception as e:
            log.error("Reliability scanner '%s' failed: %s", name, e)
            results.append(
                {
                    "scanner_name": name,
                    "score": 0.0,
                    "error": str(e),
                }
            )

    return results


__all__ = [
    "ReliabilityScanner",
    "HallucinationScanner",
    "CitationScanner",
    "ConsistencyScanner",
    "CalibrationScanner",
    "list_reliability_scanners",
    "get_reliability_scanner",
    "run_reliability_checks",
]
