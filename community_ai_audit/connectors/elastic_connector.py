"""
Elastic Security connector — Phase 2 hardened.
Streams audit findings to Elasticsearch / Elastic Security via the
bulk API with retry, validation, and DLQ fallback.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from community_ai_audit.core.interfaces import SIEMConnector
from community_ai_audit.connectors.base import (
    normalize_severity,
    chunk_list,
    validate_events,
    log_dlq_event,
    now_iso,
)
from community_ai_audit.connectors.retry import RetryConfig

log = logging.getLogger(__name__)


class ElasticConnector(SIEMConnector):
    """Connector to Elasticsearch / Elastic Security with retry support.

    Config keys:
        url (str): Elasticsearch URL. Env: ELASTICSEARCH_URL.
        api_key (str, optional): API key for auth.
        username / password (str, optional): Basic auth.
        index (str): Target index. Default: 'security-ai-audit'.
        verify_ssl (bool): Validate SSL cert. Default: True.
        max_batch_size (int): Docs per bulk request. Default: 100.
        retry (dict): RetryConfig overrides.
    """

    name = "elastic"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._client = None
        self._index: str = "security-ai-audit"
        self._verify_ssl: bool = True
        self._max_batch: int = 100
        self._retry_cfg: Optional[RetryConfig] = None

    def connect(self, config: Dict[str, Any]) -> None:
        # Lazy import to avoid hard dep if unused
        from elasticsearch import Elasticsearch

        import os
        url = config.get("url") or os.environ.get("ELASTICSEARCH_URL")
        if not url:
            raise ValueError("Set 'url' or ELASTICSEARCH_URL.")

        self._index = config.get("index", "security-ai-audit")
        self._verify_ssl = config.get("verify_ssl", True)
        self._max_batch = int(config.get("max_batch_size", 100))
        self._retry_cfg = RetryConfig.from_dict(config.get("retry"))

        # Build client kwargs
        client_kwargs = {"verify_certs": self._verify_ssl}
        if config.get("username") and config.get("password"):
            client_kwargs["basic_auth"] = (config["username"], config["password"])
        elif config.get("api_key"):
            client_kwargs["api_key"] = config["api_key"]
        elif os.environ.get("ELASTICSEARCH_API_KEY"):
            client_kwargs["api_key"] = os.environ["ELASTICSEARCH_API_KEY"]
        elif os.environ.get("ELASTICSEARCH_USERNAME") and os.environ.get("ELASTICSEARCH_PASSWORD"):
            client_kwargs["basic_auth"] = (
                os.environ["ELASTICSEARCH_USERNAME"],
                os.environ["ELASTICSEARCH_PASSWORD"],
            )

        self._client = Elasticsearch([url], **client_kwargs)

        if not self._client.ping():
            raise ConnectionError(f"Cannot connect to Elasticsearch at {url}")
        log.info("Connected to Elasticsearch at %s (index=%s)", url, self._index)

    def disconnect(self) -> None:
        self._client = None

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(
        self, events: List[Dict[str, Any]], event_type: str = "audit"
    ) -> Dict[str, Any]:
        if not events:
            return {"success": 0, "failed": 0}
        if not self._client:
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
            body_lines: List[str] = []
            for ev in batch:
                doc = self._transform_event(ev, event_type)
                body_lines.append(json.dumps({"index": {"_index": self._index}}))
                body_lines.append(json.dumps(doc))
            body = "\n".join(body_lines) + "\n"

            success, failed = self._send_bulk_inner(body, batch, event_type)
            total_success += success
            total_failed += failed

        log.info(
            "Sent %d events to Elastic (index=%s): success=%d failed=%d",
            len(events), self._index, total_success, total_failed,
        )
        return {"success": total_success, "failed": total_failed}

    def _send_bulk_inner(self, body: str, events: List[Dict], event_type: str) -> tuple[int, int]:
        """Execute a single bulk request with retry."""
        from community_ai_audit.connectors.retry import retry
        import time, random

        max_attempts = self._retry_cfg.max_attempts if self._retry_cfg and self._retry_cfg.enabled else 1
        initial_delay = self._retry_cfg.initial_delay if self._retry_cfg else 1.0
        max_delay = self._retry_cfg.max_delay if self._retry_cfg else 60.0
        exp_base = self._retry_cfg.exponential_base if self._retry_cfg else 2.0
        jitter = self._retry_cfg.jitter if self._retry_cfg else 0.25

        delay = initial_delay
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self._client.bulk(body=body)
                if resp.get("errors"):
                    # Count per-item errors
                    items = resp.get("items", [])
                    success = sum(1 for it in items if not it.get("index", {}).get("error"))
                    failed = len(items) - success
                    # Log failures as DLQ
                    for i, it in enumerate(items):
                        if err := it.get("index", {}).get("error"):
                            log_dlq_event(
                                events[i] if i < len(events) else {},
                                f"elastic_bulk_error:{err.get('type')}",
                            )
                    return success, failed
                else:
                    return len(events), 0  # all succeeded
            except Exception as exc:  # broad to catch transport/connection errors
                if attempt == max_attempts:
                    for ev in events:
                        log_dlq_event(ev, f"elastic_max_retries:{type(exc).__name__}")
                    return 0, len(events)
                # exponential backoff with jitter
                time.sleep(delay + delay * jitter * random.random())
                delay = min(delay * exp_base, max_delay)

        # fallback
        for ev in events:
            log_dlq_event(ev, "elastic_send_failed")
        return 0, len(events)

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        log.info("Query Elastic: %s", query)
        resp = self._client.search(index=self._index, q=query, size=100)
        return [hit["_source"] for hit in resp.get("hits", {}).get("hits", [])]

    def _transform_event(self, event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        severty = normalize_severity(str(event.get("severity", "info")))

        doc = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "event": {
                "kind": "alert",
                "category": ["ai-audit"],
                "type": ["info"],
                "severity": severty,
            },
            "ai": {
                "audit": {
                    "type": event_type,
                    "severity": severty,
                    "model_id": event.get("model_id"),
                    "scanner": event.get("scanner_name"),
                    "title": event.get("title"),
                    "description": event.get("description"),
                    "confidence": event.get("confidence"),
                    "evidence": event.get("evidence"),
                    "recommendation": event.get("recommendation"),
                }
            },
        }

        # Flatten other top-level fields under ai.audit.extra for now
        extra = {k: v for k, v in event.items() if k not in {
            "title", "description", "severity", "confidence", "model_id",
            "scanner_name", "evidence", "recommendation", "cwe_id", "mitre_id"
        }}
        if extra:
            doc["ai"]["audit"]["extra"] = extra

        # Common enrichment fields
        if "cwe_id" in event:
            doc["vulnerability"] = {"id": event["cwe_id"], "type": "cwe"}
        if "mitre_id" in event:
            doc["threat"] = [{"framework": "MITRE", "tactic": event["mitre_id"]}]

        return doc

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "api_key": {"type": "string"},
                "username": {"type": "string"},
                "password": {"type": "string"},
                "index": {"type": "string", "default": "security-ai-audit"},
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

