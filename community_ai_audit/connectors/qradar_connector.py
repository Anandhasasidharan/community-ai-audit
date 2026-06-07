"""
QRadar SIEM connector — pushes audit findings to IBM QRadar via the REST API.
Uses QRadar Ariel / Reference Data APIs with retry support.
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


class QRadarConnector(SIEMConnector):
    """Connector to IBM QRadar SIEM via REST API.

    Config keys:
        url (str): QRadar console URL. Falls back to env: QRADAR_URL.
        api_token (str): QRadar API token. Falls back to env: QRADAR_API_TOKEN.
        verify_ssl (bool): Validate SSL cert. Default: True.
        max_batch_size (int): Events per batch. Default: 100.
        offense_name (str): Offense name prefix. Default: "AI Audit".
        retry (dict): RetryConfig overrides.
    """

    name = "qradar"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._session: Optional[requests.Session] = None
        self._url: Optional[str] = None
        self._verify_ssl: bool = True
        self._max_batch: int = 100

    def connect(self, config: Dict[str, Any]) -> None:
        self._url = config.get("url") or os.environ.get("QRADAR_URL")
        if not self._url:
            raise ValueError("QRadar URL required. Set 'url' or QRADAR_URL.")

        api_token = config.get("api_token") or os.environ.get("QRADAR_API_TOKEN")
        if not api_token:
            raise ValueError("QRadar API token required. Set 'api_token' or QRADAR_API_TOKEN.")

        self._verify_ssl = config.get("verify_ssl", True)
        self._max_batch = int(config.get("max_batch_size", 100))
        self._offense_name = config.get("offense_name", "AI Audit")
        self._retry_cfg = RetryConfig.from_dict(config.get("retry"))

        self._session = requests.Session()
        self._session.headers.update(
            {
                "SEC": api_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        log.info("QRadar connector configured for %s", self._url)

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

        validate_events(events)
        total_success = 0
        total_failed = 0

        for batch in chunk_list(events, self._max_batch):
            # QRadar uses the offense API or custom event collector
            payload = {
                "offense_name": f"{self._offense_name} - {event_type}",
                "events": [self._transform_event(ev, event_type) for ev in batch],
            }
            success, failed = self._send_batch_inner(payload, batch)
            total_success += success
            total_failed += failed

        log.info(
            "Sent %d events to QRadar: success=%d failed=%d",
            len(events),
            total_success,
            total_failed,
        )
        return {"success": total_success, "failed": total_failed}

    def _send_batch_inner(self, payload: Dict, events: List[Dict]) -> tuple:
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
                    f"{self._url}/api/ariel/offenses",
                    data=json.dumps(payload),
                    verify=self._verify_ssl,
                    timeout=30,
                )
                resp.raise_for_status()
                return len(events), 0
            except requests.exceptions.RequestException as exc:
                status = exc.response.status_code if exc.response is not None else None

                if attempt == max_attempts:
                    for ev in events:
                        log_dlq_event(ev, f"qradar_max_retries:{status or 'error'}")
                    return 0, len(events)

                should_retry = (
                    status in DEFAULT_RETRY_STATUS
                    if self._retry_cfg and self._retry_cfg.enabled
                    else status in {429, 500, 502, 503, 504}
                )

                if should_retry:
                    time.sleep(delay + delay * jitter * random.random())
                    delay = min(delay * exp_base, max_delay)
                    log.warning("QRadar retry %d/%d after HTTP %s", attempt, max_attempts, status)
                else:
                    for ev in events:
                        log_dlq_event(ev, f"qradar_http_{status}")
                    return 0, len(events)

        for ev in events:
            log_dlq_event(ev, "qradar_send_failed")
        return 0, len(events)

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        log.info("QRadar query: %s", query)
        return [{"_raw": "query-stub", "_time": datetime.now(timezone.utc).isoformat()}]

    def _transform_event(self, event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        return {
            "name": event.get("title", "Audit Finding"),
            "description": event.get("description", ""),
            "severity": normalize_severity(str(event.get("severity", "info"))),
            "type": event_type,
            "confidence": event.get("confidence"),
            "source": "community-ai-audit",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "api_token": {"type": "string"},
                "verify_ssl": {"type": "boolean", "default": True},
                "max_batch_size": {"type": "integer", "default": 100},
                "offense_name": {"type": "string", "default": "AI Audit"},
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
