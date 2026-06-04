"""
Base connector utilities, shared schema helpers, and retry integration.
All SIEM and security tool connectors share these utilities.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from community_ai_audit.connectors.retry import RetryConfig

log = logging.getLogger(__name__)

def safe_import(module_name: str):
    """Safely import a module, returning None if not available."""
    import importlib
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None

# ─────────────────────────────────────────────────────────────
# Severity normalization
# ─────────────────────────────────────────────────────────────

SEVERITY_ORDER = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1, "unknown": 0}


def normalize_severity(severity: str) -> str:
    """Normalize any string severity representation to a canonical form.

    Args:
        severity: Raw severity string.

    Returns:
        Normalized severity ('critical', 'high', 'medium', 'low', 'info', 'unknown').
    """
    if not severity:
        return "unknown"
    s = severity.lower().strip()
    mapping = {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "warning": "medium",
        "low": "low",
        "info": "info",
        "information": "info",
        "debug": "info",
        "error": "high",  # 'error' severity maps to 'high'
    }
    return mapping.get(s, "unknown")


def severity_rank(severity: str) -> int:
    return SEVERITY_ORDER.get(normalize_severity(severity), 0)


# ─────────────────────────────────────────────────────────────
# List utilities
# ─────────────────────────────────────────────────────────────

def chunk_list(data: List[Any], size: int) -> List[List[Any]]:
    """Split a list into chunks of a specified maximum size.

    Args:
        data: List to split.
        size: Maximum chunk size (must be > 0).

    Returns:
        List of chunks.
    """
    if size <= 0:
        raise ValueError("chunk size must be positive")
    return [data[i : i + size] for i in range(0, len(data), size)]


# ─────────────────────────────────────────────────────────────
# Metadata flattening
# ─────────────────────────────────────────────────────────────

def flatten_metadata(metadata: Dict[str, Any], prefix: str = "meta_") -> Dict[str, str]:
    """Flatten a nested metadata dict into flat string key-value pairs.

    Args:
        metadata: Nested dictionary to flatten.
        prefix: Prefix to add to each key.

    Returns:
        Flattened string->string dictionary.
    """
    flat = {}
    for key, value in metadata.items():
        flat_key = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten_metadata(value, f"{flat_key}_"))
        elif isinstance(value, (list, tuple)):
            flat[flat_key] = ", ".join(str(v) for v in value)
        else:
            flat[flat_key] = str(value)
    return flat


# ─────────────────────────────────────────────────────────────
# Timestamp utilities
# ─────────────────────────────────────────────────────────────

def now_iso() -> str:
    """Return timezone-aware ISO timestamp (UTC)."""
    return datetime.now(timezone.utc).isoformat()


def timestamp_now() -> str:
    """Alias for now_iso() for backward compatibility."""
    return now_iso()


# ─────────────────────────────────────────────────────────────
# Event schema validation
# ─────────────────────────────────────────────────────────────

# Required fields for a normalized audit finding event
_REQUIRED_EVENT_FIELDS = {"title", "severity"}


def validate_event(event: Dict[str, Any], strict: bool = False) -> List[str]:
    """Validate a raw audit event dict against the schema contract.

    Args:
        event: Event dictionary to validate.
        strict: If True, warn on missing optional fields too.

    Returns:
        List of validation warning messages (empty if valid).
    """
    warnings = []
    missing = _REQUIRED_EVENT_FIELDS - set(event.keys())
    if missing:
        warnings.append(f"missing required fields: {sorted(missing)}")
    if strict:
        if "confidence" in event and not isinstance(event["confidence"], (int, float)):
            warnings.append("'confidence' should be numeric")
        if "severity" in event and normalize_severity(str(event["severity"])) == "unknown":
            warnings.append(f"unrecognized severity value: {event.get('severity')}")
    return warnings


def validate_events(events: List[Dict[str, Any]], strict: bool = False) -> Dict[str, Any]:
    """Validate a batch of events and return a summary.

    Args:
        events: List of event dicts.
        strict: If True, apply strict validation (check confidence type, etc.).

    Returns:
        Dict with 'valid', 'warnings', and per-event warning lists.
    """
    results = {"valid": 0, "warnings": 0, "events": []}
    for i, ev in enumerate(events):
        warns = validate_event(ev, strict=strict)
        if warns:
            results["warnings"] += 1
            results["events"].append({"index": i, "warnings": warns})
        else:
            results["valid"] += 1
    return results


# ─────────────────────────────────────────────────────────────
# Dead-letter / fallback helpers
# ─────────────────────────────────────────────────────────────

def log_dlq_event(event: Dict[str, Any], reason: str, logger: Optional[logging.Logger] = None) -> None:
    """Log a failed event to a dead-letter queue (stdout fallback).

    In production this should be replaced with a real DLQ (Redis, SQS, etc.).
    """
    target = logger or log
    target.error(
        "[DLQ] event dropped | reason=%s | title=%s | severity=%s",
        reason,
        event.get("title", "?"),
        event.get("severity", "?"),
    )