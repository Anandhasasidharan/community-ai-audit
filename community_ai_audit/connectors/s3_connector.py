"""
S3 cloud storage connector — stores and retrieves audit findings
as JSON objects in AWS S3 buckets.
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


class S3Connector(SIEMConnector):
    """Connector to AWS S3 for audit finding persistence.

    Config keys:
        bucket (str): S3 bucket name. Falls back to env: S3_BUCKET.
        region (str): AWS region. Falls back to env: AWS_REGION or 'us-east-1'.
        prefix (str): Key prefix. Default: 'audit/'.
        aws_access_key_id (str): Falls back to env: AWS_ACCESS_KEY_ID.
        aws_secret_access_key (str): Falls back to env: AWS_SECRET_ACCESS_KEY.
    """

    name = "s3"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._client = None
        self._bucket: Optional[str] = None
        self._prefix: str = "audit/"

    def connect(self, config: Dict[str, Any]) -> None:
        boto3 = _lazy_import()

        self._bucket = config.get("bucket") or os.environ.get("S3_BUCKET")
        if not self._bucket:
            raise ValueError("S3 bucket required. Set 'bucket' or S3_BUCKET.")

        self._region = config.get("region") or os.environ.get("AWS_REGION", "us-east-1")
        self._prefix = config.get("prefix", "audit/")

        session_kwargs: Dict[str, Any] = {"region_name": self._region}
        ak = config.get("aws_access_key_id") or os.environ.get("AWS_ACCESS_KEY_ID")
        sk = config.get("aws_secret_access_key") or os.environ.get("AWS_SECRET_ACCESS_KEY")
        if ak and sk:
            session_kwargs["aws_access_key_id"] = ak
            session_kwargs["aws_secret_access_key"] = sk

        session = boto3.Session(**session_kwargs)
        self._client = session.client("s3")
        log.info("S3 connector configured for bucket '%s'", self._bucket)

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
                key = f"{self._prefix}{event_type}/{timestamp}-{hash(str(ev))}.json"
                self._client.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=json.dumps(self._transform_event(ev, event_type), default=str),
                    ContentType="application/json",
                )
                total_success += 1
            except Exception as e:
                log.warning("S3 upload failed: %s", e)
                log_dlq_event(ev, f"s3_upload_error:{e}")
                total_failed += 1

        log.info("Uploaded %d/%d events to S3 bucket '%s'", total_success, len(events), self._bucket)
        return {"success": total_success, "failed": total_failed}

    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._client or not self._bucket:
            raise RuntimeError("Not connected.")

        try:
            prefix = f"{self._prefix}{query}/" if query else self._prefix
            resp = self._client.list_objects_v2(Bucket=self._bucket, Prefix=prefix, MaxKeys=50)
            results = []
            for obj in resp.get("Contents", []):
                obj_resp = self._client.get_object(Bucket=self._bucket, Key=obj["Key"])
                results.append(json.loads(obj_resp["Body"].read().decode()))
            return results
        except Exception as e:
            log.error("S3 query failed: %s", e)
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
                "region": {"type": "string", "default": "us-east-1"},
                "prefix": {"type": "string", "default": "audit/"},
                "aws_access_key_id": {"type": "string"},
                "aws_secret_access_key": {"type": "string"},
            },
        }


def _lazy_import():
    try:
        import boto3
        return boto3
    except ImportError:
        raise ImportError("boto3 not installed. Run: pip install boto3")
