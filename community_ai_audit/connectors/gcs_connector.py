"""
GCS cloud storage connector — stores and retrieves audit findings
as JSON objects in Google Cloud Storage buckets.
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


class GCSConnector(SIEMConnector):
    """Connector to Google Cloud Storage for audit finding persistence.

    Config keys:
        bucket (str): GCS bucket name. Falls back to env: GCS_BUCKET.
        prefix (str): Key prefix. Default: 'audit/'.
        project (str): GCP project ID. Falls back to env: GCP_PROJECT.
    """

    name = "gcs"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._client = None
        self._bucket: Optional[str] = None
        self._prefix: str = "audit/"

    def connect(self, config: Dict[str, Any]) -> None:
        storage = _lazy_import()
        self._bucket = config.get("bucket") or os.environ.get("GCS_BUCKET")
        if not self._bucket:
            raise ValueError("GCS bucket required. Set 'bucket' or GCS_BUCKET.")

        self._prefix = config.get("prefix", "audit/")
        project = config.get("project") or os.environ.get("GCP_PROJECT")

        self._client = storage.Client(project=project)
        log.info("GCS connector configured for bucket '%s'", self._bucket)

    def disconnect(self) -> None:
        self._client = None

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(self, events: List[Dict[str, Any]], event_type: str = "audit") -> Dict[str, Any]:
        if not events:
            return {"success": 0, "failed": 0}
        if not self._client or not self._bucket:
            raise RuntimeError("Not connected. Call connect() first.")

        total_success = 0
        total_failed = 0
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

        for ev in events:
            try:
                key = f"{self._prefix}{event_type}/{timestamp}-{abs(hash(str(ev)))}.json"
                bucket = self._client.bucket(self._bucket)
                blob = bucket.blob(key)
                blob.upload_from_string(
                    json.dumps(self._transform_event(ev, event_type), default=str),
                    content_type="application/json",
                )
                total_success += 1
            except Exception as e:
                log.warning("GCS upload failed: %s", e)
                log_dlq_event(ev, f"gcs_upload_error:{e}")
                total_failed += 1

        log.info(
            "Uploaded %d/%d events to GCS bucket '%s'", total_success, len(events), self._bucket
        )
        return {"success": total_success, "failed": total_failed}

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._client or not self._bucket:
            raise RuntimeError("Not connected.")

        try:
            prefix = f"{self._prefix}{query}/" if query else self._prefix
            bucket = self._client.bucket(self._bucket)
            blobs = bucket.list_blobs(prefix=prefix, max_results=50)
            results = []
            for blob in blobs:
                results.append(json.loads(blob.download_as_string()))
            return results
        except Exception as e:
            log.error("GCS query failed: %s", e)
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
                "bucket": {"type": "string"},
                "prefix": {"type": "string", "default": "audit/"},
                "project": {"type": "string"},
            },
        }


def _lazy_import():
    try:
        from google.cloud import storage

        return storage
    except ImportError:
        raise ImportError(
            "google-cloud-storage not installed. Run: pip install google-cloud-storage"
        )
