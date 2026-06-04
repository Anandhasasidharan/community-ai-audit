# Adding a New SIEM or Security Connector — Step-by-Step

> **Time to complete:** ~30 minutes
> **Goal:** Add a connector that pushes audit findings to a SIEM or security platform.

## 1. Understand the Interface

 connectors implement `SIEMConnector` (for log/event platforms) or `SecurityToolConnector` (for SOAR/ticketing). Both require:

| Method | Purpose |
|--------|---------|
| `connect(config)` | Authenticate, set up connection |
| `disconnect()` | Clean up |
| `send_event(event, event_type)` | Push a single finding |
| `send_batch(events, event_type)` | Push multiple findings in one request |
| `query(query, time_range)` | Query for historical data |
| `get_config_schema()` | Return JSON schema for config validation |

## 2. Create Your Connector File

Create `community_ai_audit/connectors/myplatform_connector.py`:

```python
"""MyPlatform SIEM connector."""

from typing import Any, Dict, List, Optional
import logging

from community_ai_audit.core.interfaces import SIEMConnector
from community_ai_audit.connectors.base import normalize_severity, now_iso

log = logging.getLogger(__name__)

class MyPlatformConnector(SIEMConnector):
    name = "myplatform"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._url: Optional[str] = None
        self._api_key: Optional[str] = None

    def connect(self, config: Dict[str, Any]) -> None:
        self._url = config.get("url") or self.config.get("url")
        self._api_key = config.get("api_key") or self.config.get("api_key")
        if not self._url:
            raise ValueError("MyPlatform URL required")
        # Optional: validate with a ping
        log.info("Connected to MyPlatform at %s", self._url)

    def disconnect(self) -> None:
        self._url = None
        self._api_key = None

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(self, events: List[Dict[str, Any]], event_type: str = "audit") -> Dict[str, Any]:
        import requests
        payload = {
            "source": "community-ai-audit",
            "events": [
                {
                    "title": ev["title"],
                    "severity": normalize_severity(ev.get("severity", "info")),
                    "description": ev.get("description", ""),
                    "timestamp": now_iso(),
                }
                for ev in events
            ],
        }
        resp = requests.post(f"{self._url}/api/v1/events", json=payload, timeout=30)
        resp.raise_for_status()
        return {"success": len(events), "failed": 0}

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        # Optional: implement querying for historical data
        return []

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "api_key": {"type": "string"},
            },
            "required": ["url"],
        }
```

## 3. Register Your Connector

Add to `community_ai_audit/connectors/__init__.py`:

```python
from .myplatform_connector import MyPlatformConnector
```

Or register dynamically in `community_ai_audit/connectors/registry.py`.

## 4. Test Your Connector

```python
from community_ai_audit.connectors.myplatform_connector import MyPlatformConnector

conn = MyPlatformConnector()
conn.connect({"url": "https://myplatform.local", "api_key": "test"})
result = conn.send_batch([{"title": "Test", "severity": "high"}])
print(result)
```

## Key Patterns

- **Batching**: Group events by severity, chunk by platform limits
- **Validation**: Use `normalize_severity()` from `connectors.base`
- **Retry**: Use the shared `RetryConfig` and `retry()` decorator
- **Dead-letter**: Log failed events with `log_dlq_event()` from `connectors.base`
- **Schema**: Always implement `get_config_schema()` for CLI validation

## Full Working Example

See `examples/minimal_connector.py` for a complete minimal connector.
