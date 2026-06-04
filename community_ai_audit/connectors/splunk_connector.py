"""
Splunk HTTP Event Collector (HEC) connector — Phase 2 hardened.
Streams audit findings to Splunk via the HEC REST endpoint with
exponential-backoff retry, event validation, and dead-letter logging.
"""

from __future__ import annotations

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
from community_ai_audit.connectors.retry import RetryConfig, DEFAULT_RETRY_STATUS

log = logging.getLogger(__name__)


class SplunkConnector(SIEMConnector):
    """Connector to Splunk HTTP Event Collector with retry support.

    Config keys:
        hec_url (str): Full HEC endpoint URL. Falls back to env: SPLUNK_HEC_URL.
        hec_token (str): HEC authentication token. Falls back to env: SPLUNK_HEC_TOKEN.
        index (str): Target Splunk index. Default: 'security'.
        sourcetype (str): Splunk sourcetype. Default: 'ai:audit'.
        verify_ssl (bool): Validate SSL cert. Default: True.
        max_batch_size (int): Events per batch. Default: 100.
        retry (dict): RetryConfig overrides (e.g. {"max_attempts": 5}).
    """

    name = "splunk"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._session: Optional[requests.Session] = None
        self._url: Optional[str] = None
        self._token: Optional[str] = None
        self._index: str = "security"
        self._sourcetype: str = "ai:audit"
        self._verify_ssl: bool = True
        self._max_batch: int = 100
        self._retry_cfg: Optional[RetryConfig] = None

    def connect(self, config: Dict[str, Any]) -> None:
        self._url = config.get("hec_url") or os.environ.get("SPLUNK_HEC_URL")
        if not self._url:
            raise ValueError(
                "Splunk HEC URL required. Set 'hec_url' or SPLUNK_HEC_URL."
            )

        self._token = config.get("hec_token") or os.environ.get("SPLUNK_HEC_TOKEN")
        if not self._token:
            raise ValueError(
                "Splunk HEC token required. Set 'hec_token' or SPLUNK_HEC_TOKEN."
            )

        self._index = config.get("index", "security")
        self._sourcetype = config.get("sourcetype", "ai:audit")
        self._verify_ssl = config.get("verify_ssl", True)
        self._max_batch = int(config.get("max_batch_size", 100))
        self._retry_cfg = RetryConfig.from_dict(config.get("retry"))

        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Splunk {self._token}",
            "Content-Type": "application/json",
        })

        # Optional health check
        health_url = f"{self._url}/services/collector/health"
        try:
            resp = self._session.get(health_url, verify=self._verify_ssl, timeout=5)
            resp.raise_for_status()
            log.info("Splunk HEC reachable at %s", self._url)
        except Exception as e:
            log.warning("Splunk HEC health check failed (non-fatal): %s", e)

    def disconnect(self) -> None:
        if self._session:
            self._session.close()
        self._session = None

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(
        self, events: List[Dict[str, Any]], event_type: str = "audit"
    ) -> Dict[str, Any]:
        if not events:
            return {"success": 0, "failed": 0}

        if not self._session or not self._url:
            raise RuntimeError("Not connected. Call connect() first.")

        # Validate events
        valid_summary = validate_events(events)
        for ev_report in valid_summary.get("events", []):
            idx = ev_report["index"]
            for w in ev_report.get("warnings", []):
                log.warning("Event %d: %s", idx, w)

        total_success = 0
        total_failed = 0

        for batch in chunk_list(events, self._max_batch):
            payload_lines: List[str] = []
            for ev in batch:
                splunk_event = self._transform_event(ev, event_type)
                payload_lines.append(json.dumps(splunk_event))

            body = "\n".join(payload_lines)

            success, failed = self._send_batch_inner(body, batch, event_type)
            total_success += success
            total_failed += failed

        log.info(
            "Sent %d events to Splunk (index=%s): success=%d failed=%d",
            len(events), self._index, total_success, total_failed,
        )
        return {"success": total_success, "failed": total_failed}

    def _send_batch_inner(self, body: str, events: List[Dict], event_type: str):
        """Single HTTP POST to Splunk HEC with retry."""
        import time
        import random

        max_attempts = self._retry_cfg.max_attempts if self._retry_cfg and self._retry_cfg.enabled else 1
        initial_delay = self._retry_cfg.initial_delay if self._retry_cfg else 1.0
        max_delay = self._retry_cfg.max_delay if self._retry_cfg else 60.0
        exp_base = self._retry_cfg.exponential_base if self._retry_cfg else 2.0
        jitter = self._retry_cfg.jitter if self._retry_cfg else 0.25

        delay = initial_delay
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self._session.post(
                    f"{self._url}/services/collector/event",
                    data=body,
                    verify=self._verify_ssl,
                    timeout=30,
                )
                resp.raise_for_status()
                response_data = resp.json()
                acknowledged = response_data.get("acknowledged", len(events))
                failed_count = len(events) - acknowledged
                return acknowledged, failed_count
            except requests.exceptions.RequestException as exc:
                status = None
                if exc.response is not None:
                    status = exc.response.status_code
                
                if attempt == max_attempts:
                    for ev in events:
                        log_dlq_event(ev, f"splunk_max_retries:{status or 'error'}")
                    return 0, len(events)
                
                # Check if status warrants retry (from DEFAULT_RETRY_STATUS)
                should_retry = (
                    status in DEFAULT_RETRY_STATUS
                    if self._retry_cfg and self._retry_cfg.enabled
                    else status in {429, 500, 502, 503, 504}
                )

                if should_retry:
                    time.sleep(delay + delay * jitter * random.random())
                    delay = min(delay * exp_base, max_delay)
                    log.warning(
                        "Splunk retry %d/%d after HTTP %s: %s",
                        attempt, max_attempts, status, exc,
                    )
                else:
                    # non-retryable -> DLQ
                    for ev in events:
                        log_dlq_event(ev, f"splunk_http_{status}")
                    return 0, len(events)

        # fallback
        for ev in events:
            log_dlq_event(ev, "splunk_send_failed")
        return 0, len(events)

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        log.info("Query Splunk: %s", query)
        # Stub — full SPL search requires additional auth setup.
        return [{"_raw": "query-stub", "_time": datetime.now(timezone.utc).isoformat()}]

    def _transform_event(self, event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        severty = normalize_severity(str(event.get("severity", "info")))

        hec_event = {
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "host": "community-ai-audit",
            "index": self._index,
            "sourcetype": self._sourcetype,
            "source": f"community-ai-audit-{event_type}",
            "event": {k: v for k, v in event.items() if k not in ("time", "host", "index", "sourcetype", "source")},
        }

        # Ensure key audit fields are embedded
        hec_event["event"]["severity"] = severty
        hec_event["event"]["audit_type"] = event_type
        hec_event["event"]["confidence"] = event.get("confidence")

        # Common Information Model fields
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
                "hec_url": {"type": "string"},
                "hec_token": {"type": "string"},
                "index": {"type": "string", "default": "security"},
                "sourcetype": {"type": "string", "default": "ai:audit"},
                "verify_ssl": {"type": "boolean", "default": True},
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

