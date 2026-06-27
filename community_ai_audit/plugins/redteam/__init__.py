from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import AttackGenerator, AttackEvaluator, AttackResult
from .jailbreak import JailbreakScanner, JailbreakAttackGenerator, JailbreakAttackEvaluator
from .multi_turn import MultiTurnAttackScanner
from .obfuscation import PromptObfuscationScanner
from .roleplay import RoleplayAttackScanner
from .exploitation import ToolExploitationScanner
from .persistence import RedTeamPersistence

log = logging.getLogger(__name__)

_BUILTIN_REDTEAM: Dict[str, type] = {
    JailbreakScanner.name: JailbreakScanner,
    MultiTurnAttackScanner.name: MultiTurnAttackScanner,
    PromptObfuscationScanner.name: PromptObfuscationScanner,
    RoleplayAttackScanner.name: RoleplayAttackScanner,
    ToolExploitationScanner.name: ToolExploitationScanner,
}


def _norm(name: str) -> str:
    return name.lower().replace("_", "-")


def list_redteam_scanners() -> List[str]:
    return sorted(_BUILTIN_REDTEAM.keys())


def get_redteam_scanner(name: str, config: Optional[Dict[str, Any]] = None):
    norm = _norm(name)
    for key, cls in _BUILTIN_REDTEAM.items():
        if _norm(key) == norm:
            return cls(config=config) if config is not None else cls()
    raise KeyError(
        f"Red team scanner '{name}' not found. Available: {list(_BUILTIN_REDTEAM.keys())}"
    )


def run_redteam_scanners(
    scanners: Optional[List[str]] = None,
    model=None,
    adapter=None,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if scanners is None:
        scanners = list_redteam_scanners()

    results: List[Dict[str, Any]] = []

    for name in scanners:
        try:
            scanner = get_redteam_scanner(name, config=config)
            result = scanner.scan(model, adapter, config=config)
            results.append(result)
            log.info(
                "Red team scanner '%s': score=%.1f success_rate=%.2f",
                name,
                result.get("score", 0),
                result.get("attack_success_rate", 0),
            )
        except KeyError:
            log.warning("Red team scanner '%s' not found, skipping", name)
        except Exception as e:
            log.error("Red team scanner '%s' failed: %s", name, e)
            results.append(
                {
                    "scanner_name": name,
                    "score": 0.0,
                    "attack_success_rate": 1.0,
                    "error": str(e),
                }
            )

    return results


__all__ = [
    "AttackGenerator",
    "AttackEvaluator",
    "AttackResult",
    "JailbreakScanner",
    "JailbreakAttackGenerator",
    "JailbreakAttackEvaluator",
    "MultiTurnAttackScanner",
    "PromptObfuscationScanner",
    "RoleplayAttackScanner",
    "ToolExploitationScanner",
    "list_redteam_scanners",
    "get_redteam_scanner",
    "run_redteam_scanners",
    "RedTeamPersistence",
]
