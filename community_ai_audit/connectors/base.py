"""
Base connector utilities and shared schema helpers.
Used by all SIEM and security tool connectors.
"""

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

def normalize_severity(severity: str) -> str:
    """Normalize a severity string to standard form.

    Args:
        severity: Raw severity string.

    Returns:
        Normalized severity ('critical', 'high', 'medium', 'low', 'info').
    """
    mapping = {
        "critical": "critical", "Critical": "critical", "CRITICAL": "critical",
        "high": "high", "High": "high", "HIGH": "high", "error": "high", "Error": "high",
        "medium": "medium", "Medium": "medium", "MEDIUM": "medium", "warning": "medium", "Warning": "medium",
        "low": "low", "Low": "low", "LOW": "low",
        "info": "info", "Info": "info", "INFO": "info", "information": "info", "Information": "info",
        "debug": "info", "Debug": "info", "DEBUG": "info",
    }
    return mapping.get(severity, "unknown")


def chunk_list(data: List[Any], size: int) -> List[List[Any]]:
    """Split a list into chunks of a specified maximum size.

    Args:
        data: List to split.
        size: Maximum chunk size.

    Returns:
        List of chunks.
    """
    return [data[i : i + size] for i in range(0, len(data), size)]


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
