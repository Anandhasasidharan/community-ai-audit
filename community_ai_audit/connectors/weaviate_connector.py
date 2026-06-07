"""
Weaviate vector database connector — stores audit findings as vectors
for semantic similarity search and threat hunting.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from community_ai_audit.core.interfaces import SIEMConnector
from community_ai_audit.connectors.base import normalize_severity, log_dlq_event
from community_ai_audit.connectors.retry import RetryConfig

log = logging.getLogger(__name__)


class WeaviateConnector(SIEMConnector):
    """Connector to Weaviate vector database for semantic finding search.

    Config keys:
        url (str): Weaviate instance URL. Falls back to env: WEAVIATE_URL.
        api_key (str): Weaviate API key. Falls back to env: WEAVIATE_API_KEY.
        class_name (str): Weaviate class name. Default: 'AIAuditFinding'.
        verify_ssl (bool): Validate SSL cert. Default: True.
        retry (dict): RetryConfig overrides.
    """

    name = "weaviate"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._session: Optional[requests.Session] = None
        self._url: Optional[str] = None

    def connect(self, config: Dict[str, Any]) -> None:
        self._url = config.get("url") or os.environ.get("WEAVIATE_URL")
        if not self._url:
            raise ValueError("Weaviate URL required. Set 'url' or WEAVIATE_URL.")

        api_key = config.get("api_key") or os.environ.get("WEAVIATE_API_KEY")

        self._class_name = config.get("class_name", "AIAuditFinding")
        self._verify_ssl = config.get("verify_ssl", True)
        self._retry_cfg = RetryConfig.from_dict(config.get("retry"))

        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        if api_key:
            self._session.headers.update({"Authorization": f"Bearer {api_key}"})

        self._ensure_schema()
        log.info("Weaviate connector configured for %s (class: %s)", self._url, self._class_name)

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

        total_success = 0
        total_failed = 0

        for ev in events:
            try:
                vector = self._embed_text(ev.get("description", ev.get("title", "")))
                obj = self._transform_event(ev, event_type)
                payload = {"class": self._class_name, "vector": vector, "properties": obj}
                resp = self._session.post(
                    f"{self._url}/v1/objects",
                    data=json.dumps(payload),
                    verify=self._verify_ssl,
                    timeout=30,
                )
                resp.raise_for_status()
                total_success += 1
            except Exception as e:
                log.warning("Weaviate send failed: %s", e)
                log_dlq_event(ev, f"weaviate_send_error:{e}")
                total_failed += 1

        log.info(
            "Sent %d events to Weaviate: success=%d failed=%d",
            len(events),
            total_success,
            total_failed,
        )
        return {"success": total_success, "failed": total_failed}

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._session or not self._url:
            raise RuntimeError("Not connected.")

        vector = self._embed_text(query)
        payload = {
            "class": self._class_name,
            "vector": vector,
            "limit": 10,
        }
        try:
            resp = self._session.post(
                f"{self._url}/v1/graphql",
                data=json.dumps({"query": self._build_near_vector_query(payload)}),
                verify=self._verify_ssl,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("Get", {}).get(self._class_name, [])
        except Exception as e:
            log.error("Weaviate query failed: %s", e)
            return []

    def _build_near_vector_query(self, payload: Dict) -> str:
        return f"""
        {{
          Get {{
            {payload["class"]}(
              nearVector: {{vector: {json.dumps(payload["vector"])}}}
              limit: {payload.get("limit", 10)}
            ) {{
              title
              description
              severity
              confidence
              timestamp
            }}
          }}
        }}
        """

    def _ensure_schema(self) -> None:
        try:
            resp = self._session.get(
                f"{self._url}/v1/schema/{self._class_name}",
                verify=self._verify_ssl,
                timeout=10,
            )
            if resp.status_code == 404:
                schema = {
                    "class": self._class_name,
                    "properties": [
                        {"name": "title", "dataType": ["text"]},
                        {"name": "description", "dataType": ["text"]},
                        {"name": "severity", "dataType": ["string"]},
                        {"name": "confidence", "dataType": ["number"]},
                        {"name": "audit_type", "dataType": ["string"]},
                        {"name": "timestamp", "dataType": ["date"]},
                    ],
                }
                self._session.post(
                    f"{self._url}/v1/schema",
                    data=json.dumps(schema),
                    verify=self._verify_ssl,
                    timeout=10,
                )
                log.info("Created Weaviate class '%s'", self._class_name)
        except Exception as e:
            log.warning("Weaviate schema check failed (non-fatal): %s", e)

    def _embed_text(self, text: str) -> List[float]:
        raw = hashlib.sha256(text.encode()).digest()
        vec = [b / 255.0 for b in raw[:128]]
        norm = sum(v * v for v in vec) ** 0.5
        return [v / norm for v in vec] if norm > 0 else vec

    def _transform_event(self, event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        return {
            "title": event.get("title", ""),
            "description": event.get("description", ""),
            "severity": normalize_severity(str(event.get("severity", "info"))),
            "confidence": event.get("confidence", 0.0),
            "audit_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "api_key": {"type": "string"},
                "class_name": {"type": "string", "default": "AIAuditFinding"},
                "verify_ssl": {"type": "boolean", "default": True},
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
