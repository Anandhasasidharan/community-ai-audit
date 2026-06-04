"""
Base utilities for model adapters.
Subclasses should inherit from the appropriate core interface directly.
"""

from typing import Any, Optional
import logging

log = logging.getLogger(__name__)


def resolve_device(device: str = "auto") -> str:
    """Resolve the best compute device available."""
    import torch

    if device == "auto":
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    return device


def safe_import(module_name: str, package: Optional[str] = None) -> Any:
    """Try to import a module, return None if not available."""
    import importlib

    try:
        return importlib.import_module(module_name, package=package)
    except ImportError:
        return None
