"""
Webhook connector — pushes audit findings to any HTTP/S endpoint.
Supports custom headers, auth tokens, and retry with exponential backoff.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import requests

from community_ai_audit.core.interfaces import SIEMConnector
from community_ai_audit.connectors.base import log_dlq_event
from community_ai_audit.connectors.retry import RetryConfig, DEFAULT_RETRY_STATUS

log = logging.getLogger(__name__)


class WebhookConnector(SIEMConnector):
    """Connector that POSTs audit findings to a configurable webhook URL.

    Config keys:
        url (str): Webhook endpoint URL. Falls back to env: WEBHOOK_URL.
        headers (dict): Custom HTTP headers (e.g. {"X-Api-Key": "..."}).
        auth_token (str): Bearer token for Authorization header.
        timeout (int): Request timeout in seconds. Default: 15.
        retry (dict): RetryConfig overrides.
    """

    name = "webhook"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._session: Optional[requests.Session] = None
        self._url: Optional[str] = None

    def connect(self, config: Dict[str, Any]) -> None:
        self._url = config.get("url") or os.environ.get("WEBHOOK_URL")
        if not self._url:
            raise ValueError("Webhook URL required. Set 'url' or WEBHOOK_URL env var.")

        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

        extra_headers = config.get("headers", {})
        if isinstance(extra_headers, dict):
            self._session.headers.update(extra_headers)

        auth_token = config.get("auth_token") or os.environ.get("WEBHOOK_AUTH_TOKEN")
        if auth_token:
            self._session.headers.update({"Authorization": f"Bearer {auth_token}"})

        self._timeout = int(config.get("timeout", 15))
        self._retry_cfg = RetryConfig.from_dict(config.get("retry"))

        log.info("Webhook connector configured for %s", self._url)

    def disconnect(self) -> None:
        if self._session:
            self._session.close()
        self._session = None

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(self, events: List[Dict[str, Any]], event_type: str = "audit") -> Dict[str, Any]:
        if not events:
            return {"success": 0, "failed": 0}
        payload = {
            "event_type": event_type,
            "events": events,
            "timestamp": __import__("datetime")
            .datetime.now(__import__("datetime").timezone.utc)
            .isoformat(),
        }
        success = self._send(payload)
        return {"success": len(events) if success else 0, "failed": 0 if success else len(events)}

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        log.info("Webhook query: %s", query)
        return []

    def push_finding(self, finding: Dict[str, Any]) -> bool:
        return self._send(finding)

    def pull_context(self, indicator: str) -> Dict[str, Any]:
        raise NotImplementedError("Webhook connector is push-only.")

    def _send(self, payload: Dict[str, Any]) -> bool:
        if not self._session or not self._url:
            raise RuntimeError("Not connected. Call connect() first.")

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
                    data=json.dumps(payload),
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                return True
            except requests.exceptions.RequestException as exc:
                status = exc.response.status_code if exc.response is not None else None

                if attempt == max_attempts:
                    log_dlq_event(payload, f"webhook_max_retries:{status or 'error'}")
                    return False

                should_retry = (
                    status in DEFAULT_RETRY_STATUS
                    if self._retry_cfg and self._retry_cfg.enabled
                    else status in {429, 500, 502, 503, 504}
                )

                if should_retry:
                    time.sleep(delay + delay * jitter * random.random())
                    delay = min(delay * exp_base, max_delay)
                    log.warning("Webhook retry %d/%d after HTTP %s", attempt, max_attempts, status)
                else:
                    log_dlq_event(payload, f"webhook_http_{status}")
                    return False

        return False

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "headers": {"type": "object"},
                "auth_token": {"type": "string"},
                "timeout": {"type": "integer", "default": 15},
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
