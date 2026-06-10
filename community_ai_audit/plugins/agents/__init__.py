from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import AgentScanner
from .tool_abuse import ToolAbuseScanner
from .memory_poisoning import MemoryPoisoningScanner
from .goal_drift import GoalDriftScanner
from .permission_escalation import PermissionEscalationScanner
from .unsafe_action import UnsafeActionScanner

log = logging.getLogger(__name__)

_BUILTIN_AGENT_SCANNERS: Dict[str, type] = {
    ToolAbuseScanner.name: ToolAbuseScanner,
    MemoryPoisoningScanner.name: MemoryPoisoningScanner,
    GoalDriftScanner.name: GoalDriftScanner,
    PermissionEscalationScanner.name: PermissionEscalationScanner,
    UnsafeActionScanner.name: UnsafeActionScanner,
}


def list_agent_scanners() -> List[str]:
    return sorted(_BUILTIN_AGENT_SCANNERS.keys())


def _norm(name: str) -> str:
    return name.lower().replace("_", "-")


def get_agent_scanner(name: str, config: Optional[Dict[str, Any]] = None) -> AgentScanner:
    norm = _norm(name)
    for key, cls in _BUILTIN_AGENT_SCANNERS.items():
        if _norm(key) == norm:
            return cls(config=config) if config is not None else cls()
    raise KeyError(
        f"Agent scanner '{name}' not found. Available: {list(_BUILTIN_AGENT_SCANNERS.keys())}"
    )


def run_agent_scanners(
    scanners: Optional[List[str]] = None,
    session=None,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Run a list of agent scanners on a session and return results.

    Args:
        scanners: Scanner names to run. None = all.
        session: An AgentAuditSession instance.
        config: Optional config dict passed to each scanner.

    Returns:
        List of scanner result dicts.
    """
    if scanners is None:
        scanners = list_agent_scanners()

    results: List[Dict[str, Any]] = []

    for name in scanners:
        try:
            scanner = get_agent_scanner(name, config=config)
            result = scanner.scan(session, config=config)
            results.append(result)
            log.info(
                "Agent scanner '%s' completed: score=%.1f findings=%d",
                name,
                result.get("score", 0),
                len(result.get("findings", [])),
            )
        except KeyError:
            log.warning("Agent scanner '%s' not found, skipping", name)
        except Exception as e:
            log.error("Agent scanner '%s' failed: %s", name, e)
            results.append(
                {
                    "scanner_name": name,
                    "score": 0.0,
                    "findings": [],
                    "error": str(e),
                }
            )

    return results


__all__ = [
    "AgentScanner",
    "ToolAbuseScanner",
    "MemoryPoisoningScanner",
    "GoalDriftScanner",
    "PermissionEscalationScanner",
    "UnsafeActionScanner",
    "list_agent_scanners",
    "get_agent_scanner",
    "run_agent_scanners",
]
