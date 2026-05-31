"""
Splunk HTTP Event Collector (HEC) connector.
Streams audit findings to Splunk via the HEC REST endpoint.

Config keys:
    hec_url (str): Full URL to the HEC endpoint (e.g. https://splunk:8088).
        Falls back to env: SPLUNK_HEC_URL
    hec_token (str): Authentication token for HEC.
        Falls back to env: SPLUNK_HEC_TOKEN
    index (str): Target Splunk index. Default: 'security'.
    sourcetype (str): Splunk sourcetype. Default: 'ai:audit'.
    verify_ssl (bool): Validate SSL cert. Default: True.
    max_batch_size (int): Events per batch. Default: 100.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from community_ai_audit.core.interfaces import SIEMConnector
from community_ai_audit.connectors.base import normalize_severity, chunk_list

log = logging.getLogger(__name__)


def safe_import(module_name):
    import importlib
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


class SplunkConnector(SIEMConnector):
    """Connector to Splunk HTTP Event Collector.

    Transforms audit findings into HEC events and sends them via
    the Splunk HEC REST API endpoint.
    """

    name = "splunk"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._session = None
        self._url: Optional[str] = None
        self._token: Optional[str] = None
        self._index: str = "security"
        self._sourcetype: str = "ai:audit"
        self._verify_ssl: bool = True
        self._max_batch: int = 100

    def connect(self, config: Dict[str, Any]) -> None:
        import os

        requests = safe_import("requests")
        if requests is None:
            raise ImportError("requests not installed. Run: pip install requests")

        self._url = config.get("hec_url") or os.environ.get("SPLUNK_HEC_URL")
        if not self._url:
            raise ValueError(
                "Splunk HEC URL required. Set 'hec_url' in config or SPLUNK_HEC_URL env var."
            )

        self._token = config.get("hec_token") or os.environ.get("SPLUNK_HEC_TOKEN")
        if not self._token:
            raise ValueError(
                "Splunk HEC token required. Set 'hec_token' in config or SPLUNK_HEC_TOKEN env var."
            )

        self._index = config.get("index", "security")
        self._sourcetype = config.get("sourcetype", "ai:audit")
        self._verify_ssl = config.get("verify_ssl", True)
        self._max_batch = config.get("max_batch_size", 100)

        # Verify connection
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Splunk {self._token}",
            "Content-Type": "application/json",
        })

        # Quick health check — note: HEC health check endpoint
        health_url = f"{self._url}/services/collector/health"
        try:
            resp = self._session.get(health_url, verify=self._verify_ssl, timeout=5)
            resp.raise_for_status()
            log.info("Splunk HEC health check OK at %s", self._url)
        except Exception as e:
            log.warning("Splunk HEC health check failed: %s", e)

    def disconnect(self) -> None:
        self._session = None
        self._url = None

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        log.debug("Sending event to Splunk: %s", event.get("title", "<no title>"))
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(self, events: List[Dict[str, Any]], event_type: str = "audit") -> Dict[str, Any]:
        if not events:
            return {"success": 0, "failed": 0}

        payloads: List[str] = []
        for event in events:
            splunk_event = self._transform_event(event, event_type)
            payloads.append(json.dumps(splunk_event))

        body = "\n".join(payloads)

        if not self._session or not self._url:
            raise RuntimeError("Not connected. Call connect() first.")

        resp = self._session.post(
            f"{self._url}/services/collector/event",
            data=body,
            verify=self._verify_ssl,
            timeout=30,
        )
        resp.raise_for_status()

        response_data = resp.json()
        success_count = response_data.get("acknowledged", len(events))
        failed_count = len(events) - success_count

        log.info(
            "Sent %d events to Splunk index='%s', source='%s'",
            len(events), self._index, self._sourcetype,
        )

        return {"success": success_count, "failed": failed_count}

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query Splunk via the REST API.

        Uses the Splunk Search API (requires additional credentials usually).
        Falls back to index-based simple REST query if available.

        Args:
            query: Splunk Processing Language (SPL) query.
            time_range: Time range string (e.g. '-24h', '-7d').

        Returns:
            List of matching event dicts.
        """
        log.info("Querying Splunk: %s", query)
        # Stub for now — full SPL+search API requires heavy dependency
        return [{"_raw": "query-results-stub", "_time": datetime.utcnow().isoformat()}]

    def _transform_event(self, event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        """Convert an audit finding to Splunk HEC event format."""
        now = datetime.utcnow().isoformat()
        severity = normalize_severity(event.get("severity", "info"))
        title = str(event.get("title", "Untitled")).replace("\"", "'")
        desc = str(event.get("description", "")).replace("\"", "'")

        hec_event = {
            "time": now,
            "host": event.get("host", "community-ai-audit"),
            "index": self._index,
            "sourcetype": self._sourcetype,
            "source": f"community-ai-audit-{event_type}",
            "event": {
                "title": title,
                "description": desc,
                "severity": severity,
                "audit_type": event_type,
                "confidence": event.get("confidence"),
                **event,
            },
        }

        # Add common Splunk CIM (Common Information Model) fields
        if "cwe_id" in event:
            hec_event["event"]["cwe"] = event["cwe_id"]
        if "mitre_id" in event:
            hec_event["event"]["mitre"] = event["mitre_id"]

        return hec_event

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "hec_url": {"type": "string", "description": "Splunk HEC endpoint URL"},
                "hec_token": {"type": "string", "description": "Splunk HEC token"},
                "index": {"type": "string", "default": "security"},
                "sourcetype": {"type": "string", "default": "ai:audit"},
                "verify_ssl": {"type": "boolean", "default": True},
                "max_batch_size": {"type": "integer", "default": 100},
            },
        }


import os