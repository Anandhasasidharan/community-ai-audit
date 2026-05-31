"""
Elastic Security connector.
Streams audit findings to Elasticsearch / Elastic Security via the
Elasticsearch bulk API.

Config keys:
    url (str): Elasticsearch URL. Falls back to env: ELASTICSEARCH_URL
    api_key (str, optional): API key for auth.
    username / password (str, optional): Basic auth credentials.
    index (str): Target index. Default: 'security-ai-audit'.
    verify_ssl (bool): Validate SSL cert. Default: True.
"""

import json
import logging
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


class ElasticConnector(SIEMConnector):
    """Connector to Elasticsearch / Elastic Security.

    Sends audit findings as documents to an Elasticsearch index,
    making them searchable and compatible with Elastic Security SIEM rules.
    """

    name = "elastic"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._client = None
        self._index: str = "security-ai-audit"
        self._verify_ssl: bool = True

    def connect(self, config: Dict[str, Any]) -> None:
        elastic_client = safe_import("elasticsearch.Elasticsearch") or safe_import("elasticsearch.Elasticsearch")
        if elastic_client is None:
            raise ImportError(
                "elasticsearch not installed. Run: pip install elasticsearch"
            )

        import os
        url = config.get("url") or os.environ.get("ELASTICSEARCH_URL")
        if not url:
            raise ValueError(
                "Elasticsearch URL required. Set 'url' in config or ELASTICSEARCH_URL env var."
            )

        self._index = config.get("index", "security-ai-audit")
        self._verify_ssl = config.get("verify_ssl", True)

        # Build client kwargs
        client_kwargs = {
            "verify_certs": self._verify_ssl,
            "basic_auth": None,
        }
        if config.get("username") and config.get("password"):
            client_kwargs["basic_auth"] = (config["username"], config["password"])
        elif config.get("api_key"):
            client_kwargs["api_key"] = config["api_key"]

        # Lazy import inside connect
        from elasticsearch import Elasticsearch
        self._client = Elasticsearch([url], **client_kwargs)

        # Test connection
        if self._client.ping():
            log.info("Connected to Elasticsearch at %s (index: %s)", url, self._index)
        else:
            raise ConnectionError(f"Cannot connect to Elasticsearch at {url}")

    def disconnect(self) -> None:
        self._client = None

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        log.debug("Sending event to Elastic: %s", event.get("title", "<no title>"))
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(self, events: List[Dict[str, Any]], event_type: str = "audit") -> Dict[str, Any]:
        if not events:
            return {"success": 0, "failed": 0}

        # Build bulk payload
        bulk_body = ""
        for event in events:
            doc = self._transform_event(event, event_type)
            # _index action
            bulk_body += json.dumps({"index": {"_index": self._index}}) + "\n"
            bulk_body += json.dumps(doc) + "\n"

        resp = self._client.bulk(body=bulk_body)
        errors = resp.get("errors", True)
        items = resp.get("items", [])
        success = sum(1 for item in items if not item.get("index", {}).get("error"))
        failed = len(items) - success

        if errors:
            log.warning("Bulk insert had errors: %d success, %d failed", success, failed)
        else:
            log.info("Sent %d events to Elastic index '%s'", success, self._index)

        return {"success": success, "failed": failed}

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query Elastic using the query string DSL.

        Args:
            query: Lucene-style query string.
            time_range: Not currently used (query should include time).

        Returns:
            List of hit dicts.
        """
        log.info("Querying Elastic: %s", query)
        resp = self._client.search(index=self._index, q=query, size=100)
        return [hit["_source"] for hit in resp.get("hits", {}).get("hits", [])]

    def _transform_event(self, event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        """Convert an audit finding to Elastic document format."""
        severity = normalize_severity(event.get("severity", "info"))

        doc = {
            "@timestamp": datetime.utcnow().isoformat(),
            "event": {
                "kind": "alert",
                "category": "ai-audit",
                "type": ["info"],
                "severity": event.get("severity"),
            },
            "ai": {
                "audit_type": event_type,
                "severity": severity,
                "model_id": event.get("model_id"),
                "scanner": event.get("scanner_name"),
                "title": event.get("title"),
                "description": event.get("description"),
                "confidence": event.get("confidence"),
                "evidence": event.get("evidence"),  # shallow for now
                "recommendation": event.get("recommendation"),
                **event,
            },
        }

        # Handle common MITRE/NIST fields
        if "cwe_id" in event:
            doc["vulnerability"] = {"id": event["cwe_id"], "classification": "cwe"}
        if "mitre_id" in event:
            doc["threat"] = {"framework": "MITRE", "tactic": event["mitre_id"]}

        return doc

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Elasticsearch URL"},
                "api_key": {"type": "string", "description": "Elasticsearch API key (optional)"},
                "username": {"type": "string"},
                "password": {"type": "string"},
                "index": {"type": "string", "default": "security-ai-audit"},
                "verify_ssl": {"type": "boolean", "default": True},
            },
        }


import os