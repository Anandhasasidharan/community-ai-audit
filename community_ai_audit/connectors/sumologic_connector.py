"""
Sumo Logic HTTP Source connector — Phase 2 hardened.
Streams audit findings to Sumo Logic via its HTTP Endpoint URL with
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


class SumoLogicConnector(SIEMConnector):
    """Connector to Sumo Logic HTTP Source with retry support.

    Config keys:
        url (str): Full HTTP endpoint URL. Falls back to env: SUMO_ENDPOINT_URL.
        source_category (str): Sumo Logic source category. Default: 'community-ai-audit'.
        source_name (str): Sumo Logic source name. Default: 'community-ai-audit'.
        verify_ssl (bool): Validate SSL cert. Default: True.
        max_batch_size (int): Events per batch. Default: 100.
        retry (dict): RetryConfig overrides (e.g. {"max_attempts": 5}).
    """

    name = "sumologic"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._session: Optional[requests.Session] = None
        self._url: Optional[str] = None
        self._source_category: str = "community-ai-audit"
        self._source_name: str = "community-ai-audit"
        self._verify_ssl: bool = True
        self._max_batch: int = 100
        self._retry_cfg: Optional[RetryConfig] = None

    def connect(self, config: Dict[str, Any]) -> None:
        self._url = config.get("url") or os.environ.get("SUMO_ENDPOINT_URL")
        if not self._url:
            raise ValueError("Sumo Logic endpoint URL required. Set 'url' or SUMO_ENDPOINT_URL.")

        self._source_category = config.get("source_category", "community-ai-audit")
        self._source_name = config.get("source_name", "community-ai-audit")
        self._verify_ssl = config.get("verify_ssl", True)
        self._max_batch = int(config.get("max_batch_size", 100))
        self._retry_cfg = RetryConfig.from_dict(config.get("retry"))

        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
            }
        )

    def disconnect(self) -> None:
        if self._session:
            self._session.close()
        self._session = None

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(self, events: List[Dict[str, Any]], event_type: str = "audit") -> Dict[str, Any]:
        if not events:
            return {"success": 0, "failed": 0}

        if not self._session or not self._url:
            raise RuntimeError("Not connected. Call connect() first.")

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
                sumo_event = self._transform_event(ev, event_type)
                payload_lines.append(json.dumps(sumo_event))

            body = "\n".join(payload_lines)

            success, failed = self._send_batch_inner(body, batch, event_type)
            total_success += success
            total_failed += failed

        log.info(
            "Sent %d events to Sumo Logic: success=%d failed=%d",
            len(events),
            total_success,
            total_failed,
        )
        return {"success": total_success, "failed": total_failed}

    def _send_batch_inner(self, body: str, events: List[Dict], event_type: str):
        """Single HTTP POST to Sumo Logic HTTP Source with retry."""
        import time
        import random

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
                resp = self._session.post(
                    self._url,
                    data=body,
                    verify=self._verify_ssl,
                    timeout=30,
                )
                resp.raise_for_status()
                return len(events), 0
            except requests.exceptions.RequestException as exc:
                status = None
                if exc.response is not None:
                    status = exc.response.status_code

                if attempt == max_attempts:
                    for ev in events:
                        log_dlq_event(ev, f"sumologic_max_retries:{status or 'error'}")
                    return 0, len(events)

                should_retry = (
                    status in DEFAULT_RETRY_STATUS
                    if self._retry_cfg and self._retry_cfg.enabled
                    else status in {429, 500, 502, 503, 504}
                )

                if should_retry:
                    time.sleep(delay + delay * jitter * random.random())
                    delay = min(delay * exp_base, max_delay)
                    log.warning(
                        "Sumo Logic retry %d/%d after HTTP %s: %s",
                        attempt,
                        max_attempts,
                        status,
                        exc,
                    )
                else:
                    for ev in events:
                        log_dlq_event(ev, f"sumologic_http_{status}")
                    return 0, len(events)

        for ev in events:
            log_dlq_event(ev, "sumologic_send_failed")
        return 0, len(events)

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        log.info("Query Sumo Logic: %s", query)
        return [{"_raw": "query-stub", "_time": datetime.now(timezone.utc).isoformat()}]

    def _transform_event(self, event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        severty = normalize_severity(str(event.get("severity", "info")))

        sumo_event = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "source_category": self._source_category,
            "source_name": self._source_name,
            "event": {
                k: v
                for k, v in event.items()
                if k not in ("timestamp", "source_category", "source_name")
            },
        }

        sumo_event["event"]["severity"] = severty
        sumo_event["event"]["audit_type"] = event_type
        sumo_event["event"]["confidence"] = event.get("confidence")

        if "cwe_id" in event:
            sumo_event["event"]["cwe"] = event["cwe_id"]
        if "mitre_id" in event:
            sumo_event["event"]["mitre"] = event["mitre_id"]

        return sumo_event

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "source_category": {"type": "string", "default": "community-ai-audit"},
                "source_name": {"type": "string", "default": "community-ai-audit"},
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
