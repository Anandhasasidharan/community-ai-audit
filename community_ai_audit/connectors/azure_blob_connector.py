"""
Azure Blob Storage connector — stores and retrieves audit findings
as JSON blobs in Azure Blob Storage containers.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from community_ai_audit.core.interfaces import SIEMConnector
from community_ai_audit.connectors.base import normalize_severity, log_dlq_event

log = logging.getLogger(__name__)


class AzureBlobConnector(SIEMConnector):
    """Connector to Azure Blob Storage for audit finding persistence.

    Config keys:
        connection_string (str): Azure Storage connection string. Falls back to AZURE_STORAGE_CONNECTION_STRING.
        container (str): Blob container name. Falls back to env: AZURE_CONTAINER.
        prefix (str): Blob name prefix. Default: 'audit/'.
    """

    name = "azure_blob"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._client = None
        self._container: Optional[str] = None
        self._prefix: str = "audit/"

    def connect(self, config: Dict[str, Any]) -> None:
        _lazy_import()
        from azure.storage.blob import BlobServiceClient

        conn_str = config.get("connection_string") or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if not conn_str:
            raise ValueError(
                "Azure connection string required. Set 'connection_string' or AZURE_STORAGE_CONNECTION_STRING."
            )

        self._container = config.get("container") or os.environ.get("AZURE_CONTAINER")
        if not self._container:
            raise ValueError("Azure container required. Set 'container' or AZURE_CONTAINER.")

        self._prefix = config.get("prefix", "audit/")

        self._client = BlobServiceClient.from_connection_string(conn_str)
        log.info("Azure Blob connector configured for container '%s'", self._container)

    def disconnect(self) -> None:
        self._client = None

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(self, events: List[Dict[str, Any]], event_type: str = "audit") -> Dict[str, Any]:
        if not events:
            return {"success": 0, "failed": 0}
        if not self._client or not self._container:
            raise RuntimeError("Not connected. Call connect() first.")

        total_success = 0
        total_failed = 0
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

        for ev in events:
            try:
                key = f"{self._prefix}{event_type}/{timestamp}-{abs(hash(str(ev)))}.json"
                container_client = self._client.get_container_client(self._container)
                blob_client = container_client.get_blob_client(key)
                blob_client.upload_blob(
                    json.dumps(self._transform_event(ev, event_type), default=str),
                    overwrite=True,
                )
                total_success += 1
            except Exception as e:
                log.warning("Azure Blob upload failed: %s", e)
                log_dlq_event(ev, f"azure_blob_upload_error:{e}")
                total_failed += 1

        log.info("Uploaded %d/%d events to Azure container '%s'", total_success, len(events), self._container)
        return {"success": total_success, "failed": total_failed}

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._client or not self._container:
            raise RuntimeError("Not connected.")

        try:
            prefix = f"{self._prefix}{query}/" if query else self._prefix
            container_client = self._client.get_container_client(self._container)
            blobs = container_client.list_blobs(name_starts_with=prefix)
            results = []
            for blob in blobs:
                blob_client = container_client.get_blob_client(blob.name)
                data = blob_client.download_blob().readall()
                results.append(json.loads(data))
            return results[:50]
        except Exception as e:
            log.error("Azure Blob query failed: %s", e)
            return []

    def _transform_event(self, event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        return {
            "title": event.get("title", ""),
            "description": event.get("description", ""),
            "severity": normalize_severity(str(event.get("severity", "info"))),
            "confidence": event.get("confidence"),
            "audit_type": event_type,
            "cwe_id": event.get("cwe_id"),
            "mitre_id": event.get("mitre_id"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "connection_string": {"type": "string"},
                "container": {"type": "string"},
                "prefix": {"type": "string", "default": "audit/"},
            },
        }


def _lazy_import():
    try:
        from azure.storage import blob  # noqa: F401
    except ImportError:
        raise ImportError("azure-storage-blob not installed. Run: pip install azure-storage-blob")
