"""
Base utilities for model adapters.
Subclasses should inherit from the appropriate core interface directly.
"""

from typing import Any, Dict, Optional
import logging

from community_ai_audit.core.interfaces import Severity

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


def is_text_model(model: Any) -> bool:
    """Check if a model is a text/language model by probing for common attributes."""
    return (
        hasattr(model.config, "vocab_size")
        or hasattr(model, "vocab_size")
        or hasattr(model, "wte")
    )


def get_model_device(model: Any):
    """Get the device a torch model is on, defaulting to CPU."""
    import torch

    try:
        return next(model.parameters()).device
    except Exception:
        return torch.device("cpu")


def query_model(adapter: Any, model: Any, prompt: str, **kwargs) -> str:
    """Query a model via adapter.generate() or adapter.predict()."""
    if hasattr(adapter, "generate") and callable(getattr(adapter, "generate")):
        return adapter.generate(model, prompt, **kwargs)
    if hasattr(adapter, "predict") and callable(getattr(adapter, "predict")):
        result = adapter.predict(model, {"prompt": prompt, "max_tokens": kwargs.get("max_tokens", 256), **kwargs})
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            for key in ("text", "output", "response", "generated_text", "content"):
                if key in result and isinstance(result[key], str):
                    return result[key]
            for v in result.values():
                if isinstance(v, str):
                    return v
        return str(result)
    raise TypeError("Adapter must implement generate() or predict()")


def severity_from_threshold(
    value: float,
    thresholds: Optional[Dict[str, float]],
    defaults: Optional[Dict[str, float]] = None,
) -> Severity:
    """Map a numeric value to a severity level using threshold boundaries."""
    t = thresholds or {}
    defaults = defaults or {}
    critical = t.get("critical", defaults.get("critical", 0.5))
    high = t.get("high", defaults.get("high", 0.3))
    medium = t.get("medium", defaults.get("medium", 0.15))
    low = t.get("low", defaults.get("low", 0.05))

    if value >= critical:
        return Severity.CRITICAL
    if value >= high:
        return Severity.HIGH
    if value >= medium:
        return Severity.MEDIUM
    if value >= low:
        return Severity.LOW
    return Severity.INFO
