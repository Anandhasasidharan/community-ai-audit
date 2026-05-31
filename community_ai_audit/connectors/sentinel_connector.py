"""
Microsoft Sentinel connector.
Streams audit findings to a Log Analytics workspace via the
HTTP Data Collector API (OMS API) for ingestion into Sentinel.

Config keys:
    workspace_id (str): Log Analytics workspace ID.
        Falls back to env: AZURE_LOG_ANALYTICS_WORKSPACE_ID
    shared_key (str): Primary or secondary shared key for the workspace.
        Falls back to env: AZURE_LOG_ANALYTICS_KEY
    log_type (str): Custom log table name. Default: 'AIAudit'.
    endpoint (str): Log Analytics endpoint. Default: https://<workspace_id>.ods.opinsights.azure.com
"""

import base64
import hmac
import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from community_ai_audit.core.interfaces import SIEMConnector
from community_ai_audit.connectors.base import normalize_severity

log = logging.getLogger(__name__)


def safe_import(module_name):
    import importlib
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


class SentinelConnector(SIEMConnector):
    """Connector to Microsoft Sentinel (via Log Analytics HTTP Data Collector API).

    Pushes audit findings to a custom table in the Log Analytics workspace,
    making them available for KQL queries, alerts, and playbooks in Sentinel.
    """

    name = "sentinel"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._workspace_id: Optional[str] = None
        self._shared_key: Optional[str] = None
        self._log_type: str = "AIAudit"
        self._endpoint: Optional[str] = None

    def connect(self, config: Dict[str, Any]) -> None:
        requests = safe_import("requests")
        if requests is None:
            raise ImportError("requests not installed. Run: pip install requests")

        self._workspace_id = config.get("workspace_id") or os.environ.get("AZURE_LOG_ANALYTICS_WORKSPACE_ID")
        if not self._workspace_id:
            raise ValueError(
                "Log Analytics workspace_id required. Set 'workspace_id' in config "
                "or AZURE_LOG_ANALYTICS_WORKSPACE_ID env var."
            )

        self._shared_key = config.get("shared_key") or os.environ.get("AZURE_LOG_ANALYTICS_KEY")
        if not self._shared_key:
            raise ValueError(
                "Log Analytics shared_key required. Set 'shared_key' in config "
                "or AZURE_LOG_ANALYTICS_KEY env var."
            )

        self._log_type = config.get("log_type", "AIAudit")
        # Default endpoint for public cloud
        self._endpoint = f"https://{self._workspace_id}.ods.opinsights.azure.com"
        if "endpoint" in config:
            self._endpoint = str(config["endpoint"])

        log.info("Sentinel connector connected (workspace: %s...)", self._workspace_id[:8])

    def disconnect(self) -> None:
        pass

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(self, events: List[Dict[str, Any]], event_type: str = "audit") -> Dict[str, Any]:
        import json as _json
        import requests

        if not events:
            return {"success": 0, "failed": 0}

        body = _json.dumps([self._transform_event(e, event_type) for e in events])
        method = "POST"
        date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        content_type = "application/json"
        content_length = len(body.encode("utf-8"))
        resource = f"/api/logs"
        string_to_hash = f"{method}\n{content_length}\n{content_type}\nx-ms-date:{date}\n{resource}"
        bytes_to_hash = bytes(string_to_hash, "utf-8")
        decoded_key = base64.b64decode(self._shared_key)
        encoded_hash = base64.b64encode(hmac.new(decoded_key, bytes_to_hash, digestmod=hashlib.sha256).digest()).decode("utf-8")
        authorization = f"SharedKey {self._workspace_id}:{encoded_hash}"

        headers = {
            "Content-Type": content_type,
            "Authorization": authorization,
            "Log-Type": self._log_type,
            "x-ms-date": date,
        }

        resp = requests.post(
            f"{self._endpoint}/api/logs",
            data=body,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()

        log.info("Sent %d events to Sentinel log table '%s'", len(events), self._log_type)
        return {"success": len(events), "failed": 0}

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        Kusto_query = safe_import("azure.kusto.data.KustoClient")
        if Kusto_query is not None:
            raise ImportError("azure-kusto-data not installed. Run: pip install azure-kusto-data")

        # KQL query via Log Analytics REST API
        log.info("Querying Sentinel workspace via KQL: %s", query)
        import requests

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._get_bearer_token()}",
        }
        resp = requests.post(
            f"https://api.loganalytics.azure.com/v1/workspaces/{self._workspace_id}/query",
            headers=headers,
            params={"query": query},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("tables", [])

    def _get_bearer_token(self) -> str:
        # Placeholder — full Azure auth via MSAL is heavy for now
        raise NotImplementedError("Azure AD token acquisition requires MSAL integration. Use 'query' as stub.")

    def _transform_event(self, event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        severity = normalize_severity(event.get("severity", "info"))
        return {
            "TimeGenerated": datetime.utcnow().isoformat(),
            "AuditType": event_type,
            "Severity": severity,
            "Title": event.get("title"),
            "Description": event.get("description"),
            "ModelId": event.get("model_id"),
            "Scanner": event.get("scanner_name"),
            "Confidence": event.get("confidence"),
            "Evidence": str(event.get("evidence", {}))[:5000],  # truncate for OMS
            "Recommendation": event.get("recommendation"),
            **event,
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "shared_key": {"type": "string"},
                "log_type": {"type": "string", "default": "AIAudit"},
                "endpoint": {"type": "string"},
            },
        }


import os