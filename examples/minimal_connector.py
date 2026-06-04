"""Minimal working connector example.

Demonstrates a custom SIEM connector that writes to a mock endpoint.

Run:
    python examples/minimal_connector.py
"""

from typing import Any, Dict, List, Optional
import logging

from community_ai_audit.core.interfaces import SIEMConnector
from community_ai_audit.connectors.base import normalize_severity, now_iso

log = logging.getLogger(__name__)


class MinimalConnector(SIEMConnector):
    """Stores findings to a mock HTTP endpoint (or local file)."""

    name = "minimal-demo"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._events: List[Dict[str, Any]] = []
        self._out_file: Optional[str] = None

    def connect(self, config: Dict[str, Any]) -> None:
        import os
        self._out_file = config.get("out_file") or os.environ.get("MINIMAL_OUT_FILE", "/tmp/minimal_audit.jsonl")
        log.info("Connected to minimal connector (output: %s)", self._out_file)

    def disconnect(self) -> None:
        self._out_file = None

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(self, events: List[Dict[str, Any]], event_type: str = "audit") -> Dict[str, Any]:
        import json as _json

        for ev in events:
            entry = {
                "timestamp": now_iso(),
                "event_type": event_type,
                "title": ev.get("title", "Untitled"),
                "severity": normalize_severity(ev.get("severity", "info")),
                "description": ev.get("description", ""),
            }
            self._events.append(entry)

        # Persist to file (in production, you'd call an API instead)
        if self._out_file:
            with open(self._out_file, "a") as f:
                for entry in self._events[-len(events):]:
                    f.write(_json.dumps(entry) + "\n")

        return {"success": len(events), "failed": 0}

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        return list(self._events)

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "out_file": {"type": "string", "default": "/tmp/minimal_audit.jsonl"},
            },
        }


if __name__ == "__main__":
    # Self-test
    conn = MinimalConnector()
    conn.connect({"out_file": "/tmp/test_minimal.jsonl"})
    result = conn.send_batch([{"title": "Test Finding", "severity": "high"}])
    print(f"Sent: {result}")
    all_events = conn.query("test")
    print(f"Queried: {len(all_events)} events")
