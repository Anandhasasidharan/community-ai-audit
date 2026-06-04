"""
Microsoft Sentinel connector — Phase 2 hardened.
Streams audit findings to Log Analytics via the HTTP Data Collector API
with retry, validation, and dead-letter queue fallback.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from community_ai_audit.core.interfaces import SIEMConnector
from community_ai_audit.connectors.base import (
    normalize_severity,
    chunk_list,
    validate_events,
    log_dlq_event,
)
from community_ai_audit.connectors.retry import RetryConfig

log = logging.getLogger(__name__)


class SentinelConnector(SIEMConnector):
    """Connector to Microsoft Sentinel via Log Analytics HTTP Data Collector API.

    Config keys:
        workspace_id (str): Log Analytics workspace ID. Env: AZURE_LOG_ANALYTICS_WORKSPACE_ID
        shared_key (str): Primary/shared key. Env: AZURE_LOG_ANALYTICS_KEY
        log_type (str): Custom table name. Default: 'AIAudit'.
        endpoint (str): Override endpoint (rarely needed).
        max_batch_size (int): Max records per post. Default: 100.
        retry (dict): RetryConfig overrides.
    """

    name = "sentinel"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._workspace_id: Optional[str] = None
        self._shared_key: Optional[str] = None
        self._log_type: str = "AIAudit"
        self._endpoint: Optional[str] = None
        self._max_batch: int = 100
        self._retry_cfg: Optional[RetryConfig] = None

    def connect(self, config: Dict[str, Any]) -> None:
        self._workspace_id = config.get("workspace_id") or os.environ.get(
            "AZURE_LOG_ANALYTICS_WORKSPACE_ID"
        )
        if not self._workspace_id:
            raise ValueError("Set 'workspace_id' or AZURE_LOG_ANALYTICS_WORKSPACE_ID.")

        self._shared_key = config.get("shared_key") or os.environ.get("AZURE_LOG_ANALYTICS_KEY")
        if not self._shared_key:
            raise ValueError("Set 'shared_key' or AZURE_LOG_ANALYTICS_KEY.")

        self._log_type = config.get("log_type", "AIAudit")
        if config.get("endpoint"):
            self._endpoint = str(config["endpoint"])
        else:
            self._endpoint = f"https://{self._workspace_id}.ods.opinsights.azure.com"

        self._max_batch = int(config.get("max_batch_size", 100))
        self._retry_cfg = RetryConfig.from_dict(config.get("retry"))

        log.info("Sentinel connector initialized for workspace %s...", self._workspace_id[:8])

    def disconnect(self) -> None:
        pass

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(self, events: List[Dict[str, Any]], event_type: str = "audit") -> Dict[str, Any]:
        if not events:
            return {"success": 0, "failed": 0}

        # Validate events
        valid_summary = validate_events(events)
        for ev_report in valid_summary.get("events", []):
            idx = ev_report["index"]
            for w in ev_report.get("warnings", []):
                log.warning("Event %d: %s", idx, w)

        total_success = 0
        total_failed = 0

        for batch in chunk_list(events, self._max_batch):
            success, failed = self._post_to_sentinel(batch, event_type)
            total_success += success
            total_failed += failed

        log.info(
            "Sent %d events to Sentinel (log_type=%s): success=%d failed=%d",
            len(events),
            self._log_type,
            total_success,
            total_failed,
        )
        return {"success": total_success, "failed": total_failed}

    def _post_to_sentinel(self, batch: List[Dict], event_type: str) -> tuple[int, int]:
        """Post a batch to Sentinel with retry."""
        import time
        import random

        body = json.dumps([self._transform_event(ev, event_type) for ev in batch])
        method = "POST"
        content_type = "application/json"
        content_length = len(body.encode("utf-8"))
        # RFC 1123 date
        date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        resource = "/api/logs"
        string_to_hash = f"{method}\n{content_length}\n{content_type}\nx-ms-date:{date}\n{resource}"
        bytes_to_hash = bytes(string_to_hash, "utf-8")
        decoded_key = base64.b64decode(self._shared_key)
        encoded_hash = base64.b64encode(
            hmac.new(decoded_key, bytes_to_hash, digestmod=hashlib.sha256).digest()
        ).decode("utf-8")
        authorization = f"SharedKey {self._workspace_id}:{encoded_hash}"

        headers = {
            "Content-Type": content_type,
            "Authorization": authorization,
            "Log-Type": self._log_type,
            "x-ms-date": date,
        }

        max_attempts = (
            self._retry_cfg.max_attempts if self._retry_cfg and self._retry_cfg.enabled else 1
        )
        initial_delay = self._retry_cfg.initial_delay if self._retry_cfg else 1.0
        max_delay = self._retry_cfg.max_delay if self._retry_cfg else 60.0
        exp_base = self._retry_cfg.exponential_base if self._retry_cfg else 2.0
        jitter = self._retry_cfg.jitter if self._retry_cfg else 0.25

        delay = initial_delay
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.post(
                    f"{self._endpoint}{resource}",
                    data=body,
                    headers=headers,
                    timeout=30,
                )
                resp.raise_for_status()
                # 200 OK = accepted
                return len(batch), 0
            except requests.exceptions.RequestException as exc:
                status = None
                if exc.response is not None:
                    status = exc.response.status_code

                if attempt == max_attempts:
                    for ev in batch:
                        log_dlq_event(ev, f"sentinel_max_retries:{status or 'error'}")
                    return 0, len(batch)

                # Determine if retryable (429, 5xx, or timeout/conn error)
                retryable = status in {429, 500, 502, 503, 504} or isinstance(
                    exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
                )

                if retryable:
                    time.sleep(delay + delay * jitter * random.random())
                    delay = min(delay * exp_base, max_delay)
                    log.warning(
                        "Sentinel retry %d/%d after %s: %s",
                        attempt,
                        max_attempts,
                        f"HTTP {status}" if status else type(exc).__name__,
                        exc,
                    )
                else:
                    # non-retryable -> DLQ
                    for ev in batch:
                        log_dlq_event(ev, f"sentinel_http_{status}")
                    return 0, len(batch)

        # fallback (should not hit)
        for ev in batch:
            log_dlq_event(ev, "sentinel_send_failed")
        return 0, len(batch)

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        log.info("Query Sentinel: %s", query)
        # Stub — full KQL query requires AAD token (MSAL). Keep simple for now.
        return [{"TimeGenerated": datetime.now(timezone.utc).isoformat(), "message": "query-stub"}]

    def _transform_event(self, event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        severty = normalize_severity(str(event.get("severity", "info")))

        base = {
            "TimeGenerated": datetime.now(timezone.utc).isoformat(),
            "AuditType": event_type,
            "Severity": severty,
            "Title": event.get("title"),
            "Description": event.get("description"),
            "ModelId": event.get("model_id"),
            "Scanner": event.get("scanner_name"),
            "Confidence": event.get("confidence"),
            "Evidence": str(event.get("evidence", {}))[:5000],  # truncate for ingestion limits
            "Recommendation": event.get("recommendation"),
        }
        # Merge any extra fields (avoid overwriting)
        for k, v in event.items():
            if k not in base:
                base[k] = v
        return base

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "shared_key": {"type": "string"},
                "log_type": {"type": "string", "default": "AIAudit"},
                "endpoint": {"type": "string"},
                "max_batch_size": {"type": "integer", "default": 100},
                "retry": {
                    "type": "object",
                    "properties": {
                        "max_attempts": {"type": "integer"},
                        "initial_delay": {"type": "number"},
                        "max_delay": {"type": "number"},
                    },
                },
            },
        }
