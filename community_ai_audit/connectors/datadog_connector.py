"""
Datadog SIEM connector — Phase 2 hardened.
Streams audit findings to Datadog via the Logs API with retry,
validation, and dead-letter queue fallback.
"""

from __future__ import annotations

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


class DatadogConnector(SIEMConnector):
    """Connector to Datadog Logs and Events with retry support.

    Config keys:
        dd_site (str): Datadog site (e.g. datadoghq.com). Env: DD_SITE.
        dd_api_key (str): Datadog API key. Env: DD_API_KEY.
        dd_app_key (str, optional): Datadog Application key. Env: DD_APP_KEY.
        service (str): Service name tag. Default: 'ai-audit'.
        tags (List[str]): Additional tags.
        max_batch_size (int): Logs per request. Default: 100.
        retry (dict): RetryConfig overrides.
    """

    name = "datadog"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._api_key: Optional[str] = None
        self._app_key: Optional[str] = None
        self._site: str = "datadoghq.com"
        self._service: str = "ai-audit"
        self._tags: List[str] = []
        self._max_batch: int = 100
        self._retry_cfg: Optional[RetryConfig] = None

    def connect(self, config: Dict[str, Any]) -> None:
        self._api_key = config.get("dd_api_key") or os.environ.get("DD_API_KEY")
        if not self._api_key:
            raise ValueError("Set 'dd_api_key' or DD_API_KEY.")

        self._app_key = config.get("dd_app_key") or os.environ.get("DD_APP_KEY")
        self._site = config.get("dd_site") or os.environ.get("DD_SITE", "datadoghq.com")
        self._service = config.get("service", "ai-audit")
        self._tags = list(config.get("tags", []))
        self._max_batch = int(config.get("max_batch_size", 100))
        self._retry_cfg = RetryConfig.from_dict(config.get("retry"))

        # Lightweight validation
        try:
            resp = requests.get(
                f"https://api.{self._site}/api/v1/validate",
                headers={"DD-API-KEY": self._api_key},
                timeout=10,
            )
            if resp.status_code == 200:
                log.info("Datadog API validated for site %s", self._site)
            else:
                log.warning("Datadog validation returned %s", resp.status_code)
        except Exception as e:
            log.warning("Datadog validation check failed (non-fatal): %s", e)

    def disconnect(self) -> None:
        pass

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(
        self, events: List[Dict[str, Any]], event_type: str = "audit"
    ) -> Dict[str, Any]:
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
            payload = [self._transform_event(ev, event_type) for ev in batch]

            success, failed = self._send_payload_inner(payload, batch)
            total_success += success
            total_failed += failed

        log.info(
            "Sent %d events to Datadog (site=%s): success=%d failed=%d",
            len(events), self._site, total_success, total_failed,
        )
        return {"success": total_success, "failed": total_failed}

    def _send_payload_inner(
        self, payload: List[Dict], events: List[Dict]
    ) -> tuple[int, int]:
        """Send payload to Datadog with retry."""
        import time
        import random

        headers = {
            "Content-Type": "application/json",
            "DD-API-KEY": self._api_key,
        }
        intake_url = f"https://http-intake.logs.{self._site}"

        max_attempts = self._retry_cfg.max_attempts if self._retry_cfg and self._retry_cfg.enabled else 1
        initial_delay = self._retry_cfg.initial_delay if self._retry_cfg else 1.0
        max_delay = self._retry_cfg.max_delay if self._retry_cfg else 60.0
        exp_base = self._retry_cfg.exponential_base if self._retry_cfg else 2.0
        jitter = self._retry_cfg.jitter if self._retry_cfg else 0.25

        delay = initial_delay
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.post(
                    f"{intake_url}/api/v2/logs",
                    json=payload,
                    headers=headers,
                    timeout=30,
                )
                resp.raise_for_status()
                # Datadog v2/logs returns 202 Accepted on success
                return len(payload), 0
            except requests.exceptions.RequestException as exc:
                if attempt == max_attempts:
                    for ev in events:
                        log_dlq_event(ev, f"datadog_max_retries:{type(exc).__name__}")
                    return 0, len(events)
                # Check if status warrants retry (429, 5xx)
                status = getattr(exc.response, "status_code", None) if exc.response else None
                if status in {429, 500, 502, 503, 504}:
                    time.sleep(delay + delay * jitter * random.random())
                    delay = min(delay * exp_base, max_delay)
                    log.warning(
                        "Datadog retry %d/%d after HTTP %s: %s",
                        attempt, max_attempts, status, exc,
                    )
                else:
                    # non-retryable -> DLQ
                    for ev in events:
                        log_dlq_event(ev, f"datadog_http_{status}")
                    return 0, len(events)

        # fallback
        for ev in events:
            log_dlq_event(ev, "datadog_send_failed")
        return 0, len(events)

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._app_key:
            raise ValueError("Datadog Application Key (DD_APP_KEY) required for querying")

        from datetime import datetime, timedelta

        now = datetime.now(timezone.utc)
        if time_range is None:
            from_date = now - timedelta(hours=24)
        else:
            # simple parser: -24h, -7d, etc.
            import re
            m = re.match(r"\-(\d+)([dhms])", time_range)
            if m:
                val = int(m.group(1))
                unit = m.group(2)
                if unit == "h":
                    from_date = now - timedelta(hours=val)
                elif unit == "d":
                    from_date = now - timedelta(days=val)
                elif unit == "m":
                    from_date = now - timedelta(minutes=val)
                elif unit == "s":
                    from_date = now - timedelta(seconds=val)
                else:
                    from_date = now - timedelta(hours=24)
            else:
                from_date = now - timedelta(hours=24)

        url = f"https://api.{self._site}"
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
                    "from": int(from_date.timestamp() * 1000),
                    "to": int(now.timestamp() * 1000),
                },
                "page": {"limit": 100},
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])

    def _transform_event(self, event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        severty = normalize_severity(str(event.get("severity", "info")))

        tags = [
            f"service:{self._service}",
            f"severity:{severty}",
            f"event_type:{event_type}",
            f"host:{event.get('host', 'community-ai-audit')}",
        ]
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "audit": {
                **event,
                "event_type": event_type,
            },
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dd_site": {"type": "string", "default": "datadoghq.com"},
                "dd_api_key": {"type": "string"},
                "dd_app_key": {"type": "string"},
                "service": {"type": "string", "default": "ai-audit"},
                "tags": {"type": "array", "items": {"type": "string"}},
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

