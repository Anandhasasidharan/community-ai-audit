"""
Datadog SIEM connector.
Streams audit findings to Datadog via the Logs API (HTTP intake)
or the Metrics API (for custom event metrics).

Config keys:
    dd_url (str): Datadog intake URL. Default: https://http-intake.logs.datadoghq.com
    dd_site (str): Datadog site (e.g. datadoghq.com, ddog-gov.com, datadoghq.eu).
        Falls back to env: DD_SITE. Default: datadoghq.com.
    dd_api_key (str): Datadog API key.
        Falls back to env: DD_API_KEY.
    dd_app_key (str, optional): Datadog Application key (for querying).
        Falls back to env: DD_APP_KEY.
    service (str): Service name tag. Default: 'ai-audit'.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from community_ai_audit.core.interfaces import SIEMConnector
from community_ai_audit.connectors.base import normalize_severity

log = logging.getLogger(__name__)


class DatadogConnector(SIEMConnector):
    """Connector to Datadog Logs and Events.

    Pushes audit findings as structured logs to Datadog's HTTP intake.
    Tags are attached for easy filtering and dashboarding in the SIEM.
    """

    name = "datadog"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._api_key: Optional[str] = None
        self._app_key: Optional[str] = None
        self._site: str = "datadoghq.com"
        self._service: str = "ai-audit"
        self._tags: List[str] = []

    def connect(self, config: Dict[str, Any]) -> None:
        requests = safe_import("requests")
        if requests is None:
            raise ImportError("requests not installed. Run: pip install requests")

        self._api_key = config.get("dd_api_key") or os.environ.get("DD_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Datadog API key required. Set 'dd_api_key' in config or DD_API_KEY env var."
            )

        self._app_key = config.get("dd_app_key") or os.environ.get("DD_APP_KEY")
        self._site = config.get("dd_site") or os.environ.get("DD_SITE", "datadoghq.com")
        self._service = config.get("service", "ai-audit")
        self._tags = config.get("tags", [])

        # Validate
        url = f"https://api.{self._site}"  # noqa: f-string
        try:
            resp = requests.get(
                f"{url}/api/v1/validate",
                headers={"DD-API-KEY": self._api_key},
                timeout=10,
            )
            if resp.status_code == 200:
                log.info("Datadog connection validated for site %s", self._site)
            else:
                log.warning("Datadog validation returned %s", resp.status_code)
        except Exception as e:
            log.warning("Datadog validation failed: %s", e)

    def disconnect(self) -> None:
        pass

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(self, events: List[Dict[str, Any]], event_type: str = "audit") -> Dict[str, Any]:
        import requests

        if not events:
            return {"success": 0, "failed": 0}

        # Build log array for Datadog v2 API
        logs = [self._transform_event(e, event_type) for e in events]

        headers = {
            "Content-Type": "application/json",
            "DD-API-KEY": self._api_key,
        }
        intake_url = f"https://http-intake.logs.{self._site}"  # noqa: f-string

        resp = requests.post(
            f"{intake_url}/api/v2/logs",
            json=logs,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()

        log.info("Sent %d events to Datadog (site: %s)", len(events), self._site)
        return {"success": len(events), "failed": 0}

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        # Datadog Logs API requires app key for querying
        import requests

        if not self._app_key:
            raise ValueError("Datadog Application Key (DD_APP_KEY) required for querying")

        # Convert time_range to from/to timestamps
        from_date, to_date = self._parse_time_range(time_range)

        url = f"https://api.{self._site}"  # noqa: f-string
        resp = requests.post(
            f"{url}/api/v2/logs/events/search",
            headers={
                "DD-API-KEY": self._api_key,
                "DD-APPLICATION-KEY": self._app_key,
                "Content-Type": "application/json",
            },
            json={
                "filter": {
                    "query": query,
                    "from": from_date,
                    "to": to_date,
                },
                "page": {"limit": 100},
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])

    def _transform_event(self, event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        severity = normalize_severity(event.get("severity", "info"))
        tags = [f"service:{self._service}", f"severity:{severity}", f"event_type:{event_type}"]
        if "cwe_id" in event:
            tags.append(f"cwe:{event['cwe_id']}")
        if "mitre_id" in event:
            tags.append(f"mitre:{event['mitre_id']}")
        tags.extend(self._tags)

        return {
            "ddsource": "community-ai-audit",
            "ddtags": ",".join(tags),
            "service": self._service,
            "hostname": event.get("host", "community-ai-audit"),
            "message": event.get("description", event.get("title", "")),
            "timestamp": datetime.utcnow().isoformat(),
            "audit": {
                **event,
                "event_type": event_type,
            },
        }

    @staticmethod
    def _parse_time_range(time_range: Optional[str]) -> tuple:
        import re
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        if time_range is None:
            return (now - timedelta(hours=24)).isoformat(), now.isoformat()

        m = re.match(r"\-(\d+)([dhms]?)", time_range or "-24h")
        if not m:
            return (now - timedelta(hours=24)).isoformat(), now.isoformat()

        n = int(m.group(1))
        unit = m.group(2) or "h"
        if unit == "h":
            from_date = now - timedelta(hours=n)
        elif unit == "d":
            from_date = now - timedelta(days=n)
        elif unit == "m":
            from_date = now - timedelta(minutes=n)
        else:
            from_date = now - timedelta(seconds=n)

        return from_date.isoformat(), now.isoformat()

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dd_url": {"type": "string", "description": "Datadog logs intake URL (optional, auto from site)"},
                "dd_site": {"type": "string", "default": "datadoghq.com"},
                "dd_api_key": {"type": "string"},
                "dd_app_key": {"type": "string"},
                "service": {"type": "string", "default": "ai-audit"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        }


def safe_import(module_name):
    import importlib
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


import os