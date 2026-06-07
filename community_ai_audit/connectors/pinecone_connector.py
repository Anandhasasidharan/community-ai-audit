"""
Pinecone vector database connector — stores audit findings as vectors
for similarity search and retrieval-augmented analysis.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from community_ai_audit.core.interfaces import SIEMConnector
from community_ai_audit.connectors.base import (
    normalize_severity,
    log_dlq_event,
)
from community_ai_audit.connectors.retry import RetryConfig

log = logging.getLogger(__name__)


class PineconeConnector(SIEMConnector):
    """Connector to Pinecone vector database for audit finding storage
    and similarity search.

    Config keys:
        api_key (str): Pinecone API key. Falls back to PINECONE_API_KEY env var.
        environment (str): Pinecone environment. Falls back to PINECONE_ENVIRONMENT env var.
        index_name (str): Target index name. Default: 'ai-audit'.
        dimension (int): Vector dimension. Default: 1536.
        metric (str): Distance metric. Default: 'cosine'.
        retry (dict): RetryConfig overrides (e.g. {"max_attempts": 5}).
    """

    name = "pinecone"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._client: Any = None
        self._index: Any = None
        self._index_name: str = "ai-audit"
        self._dimension: int = 1536
        self._metric: str = "cosine"
        self._retry_cfg: Optional[RetryConfig] = None

    def connect(self, config: Dict[str, Any]) -> None:
        api_key = config.get("api_key") or os.environ.get("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("Pinecone API key required. Set 'api_key' or PINECONE_API_KEY.")

        environment = config.get("environment") or os.environ.get("PINECONE_ENVIRONMENT")
        if not environment:
            raise ValueError(
                "Pinecone environment required. Set 'environment' or PINECONE_ENVIRONMENT."
            )

        self._index_name = config.get("index_name", "ai-audit")
        self._dimension = int(config.get("dimension", 1536))
        self._metric = config.get("metric", "cosine")
        self._retry_cfg = RetryConfig.from_dict(config.get("retry"))

        pinecone = self._lazy_import_pinecone()
        self._client = pinecone.Pinecone(api_key=api_key, environment=environment)

        existing_indexes = [idx.name for idx in self._client.list_indexes()]
        if self._index_name not in existing_indexes:
            log.info("Creating Pinecone index '%s'", self._index_name)
            self._client.create_index(
                name=self._index_name,
                dimension=self._dimension,
                metric=self._metric,
            )

        self._index = self._client.Index(self._index_name)
        log.info(
            "Connected to Pinecone index '%s' (%d dimensions, metric=%s)",
            self._index_name,
            self._dimension,
            self._metric,
        )

    def disconnect(self) -> None:
        self._client = None
        self._index = None

    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        return self.send_batch([event], event_type=event_type)["success"] == 1

    def send_batch(self, events: List[Dict[str, Any]], event_type: str = "audit") -> Dict[str, Any]:
        if not events:
            return {"success": 0, "failed": 0}

        if not self._index:
            raise RuntimeError("Not connected. Call connect() first.")

        vectors = []
        failed = 0
        for ev in events:
            try:
                vector_record = self._transform_event(ev, event_type)
                vectors.append(vector_record)
            except Exception as exc:
                log.warning("Failed to transform event: %s", exc)
                log_dlq_event(ev, f"pinecone_transform_error:{exc}")
                failed += 1

        if not vectors:
            return {"success": 0, "failed": len(events)}

        try:
            self._index.upsert(vectors=vectors)
            log.info(
                "Upserted %d vectors to Pinecone index '%s'",
                len(vectors),
                self._index_name,
            )
            return {"success": len(vectors), "failed": failed + len(events) - len(vectors) - failed}
        except Exception as exc:
            log.error("Pinecone upsert failed: %s", exc)
            for ev in events:
                log_dlq_event(ev, f"pinecone_upsert_error:{exc}")
            return {"success": 0, "failed": len(events)}

    def query(
        self, embedding_vector: List[float], top_k: int = 10, **kwargs
    ) -> List[Dict[str, Any]]:
        """Perform similarity search against the index.

        Args:
            embedding_vector: Query vector to search with.
            top_k: Number of nearest neighbors to return.
            **kwargs: Additional Pinecone query parameters.

        Returns:
            List of matching event records with metadata.
        """
        if not self._index:
            raise RuntimeError("Not connected. Call connect() first.")

        results = self._index.query(
            vector=embedding_vector,
            top_k=top_k,
            include_metadata=True,
            **kwargs,
        )

        matches = []
        for match in results.matches:
            matches.append(
                {
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata or {},
                }
            )

        return matches

    def _lazy_import_pinecone(self):
        """Lazily import the pinecone package."""
        try:
            import pinecone  # noqa: F811

            return pinecone
        except ImportError:
            raise ImportError(
                "Pinecone client not installed. Install with: pip install pinecone-client"
            )

    def _embed_text(self, text: str) -> List[float]:
        """Produce a deterministic float vector from text using hashing.

        Args:
            text: Input text to embed.

        Returns:
            Float vector of length self._dimension.
        """
        import struct

        vector: List[float] = []
        salt = 0
        while len(vector) < self._dimension:
            h_salted = hashlib.sha256(text.encode("utf-8") + struct.pack(">I", salt))
            hash_bytes = h_salted.digest()
            for i in range(0, len(hash_bytes), 4):
                if len(vector) >= self._dimension:
                    break
                chunk = hash_bytes[i : i + 4]
                if len(chunk) < 4:
                    chunk = chunk + b"\x00" * (4 - len(chunk))
                val = struct.unpack(">I", chunk)[0]
                normalized = (val / 2**32) * 2.0 - 1.0
                vector.append(normalized)
            salt += 1

        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]

        return vector

    def _transform_event(self, event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        severity = normalize_severity(str(event.get("severity", "info")))

        text = f"{event.get('title', '')} {event.get('description', '')}"
        vector = self._embed_text(text)

        metadata = {
            "title": event.get("title", ""),
            "description": event.get("description", ""),
            "severity": severity,
            "audit_type": event_type,
            "confidence": event.get("confidence"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "community-ai-audit",
        }

        if "cwe_id" in event:
            metadata["cwe_id"] = event["cwe_id"]
        if "mitre_id" in event:
            metadata["mitre_id"] = event["mitre_id"]
        if "nist_id" in event:
            metadata["nist_id"] = event["nist_id"]
        if "recommendation" in event:
            metadata["recommendation"] = event["recommendation"]

        record_id = hashlib.md5(
            f"{event.get('title', '')}:{event.get('description', '')}:{event_type}".encode()
        ).hexdigest()

        return {
            "id": record_id,
            "values": vector,
            "metadata": metadata,
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "api_key": {"type": "string"},
                "environment": {"type": "string"},
                "index_name": {"type": "string", "default": "ai-audit"},
                "dimension": {"type": "integer", "default": 1536},
                "metric": {"type": "string", "default": "cosine"},
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
