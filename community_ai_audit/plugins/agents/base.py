from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class AgentScanner(ABC):
    """Abstract base for agent-level auditing scanners.

    Agent scanners evaluate an agent session for security, safety,
    and behavioral issues including tool abuse, memory poisoning,
    goal drift, permission escalation, and unsafe actions.
    """

    name: str = "base_agent_scanner"
    description: str = ""
    version: str = "0.1.0"

    @abstractmethod
    def scan(
        self,
        session: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run an agent audit scan on a completed agent session.

        Args:
            session: An AgentAuditSession instance with recorded steps.
            config: Optional scanner-specific configuration.

        Returns:
            Dict with at minimum:
                - scanner_name: str
                - score: float (0-100, higher = safer)
                - findings: list of dicts with details
                - details: dict of metric-specific results
        """
        raise NotImplementedError
