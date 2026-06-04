"""
OpenAI adapter — works with OpenAI models via the official API
(ChatCompletions + Completions endpoints).
"""

from typing import Any, Dict, Optional
import logging

from community_ai_audit.core.interfaces import TextModelAdapter, ModelType

log = logging.getLogger(__name__)

openai = None


def _lazy_import():
    global openai
    if openai is None:
        openai = safe_import("openai")
        if openai is None:
            raise ImportError("openai not installed. Run: pip install openai")


def safe_import(name, package=None):
    import importlib
    try:
        return importlib.import_module(name, package=package)
    except ImportError:
        return None


class OpenAIAdapter(TextModelAdapter):
    """Adapter for OpenAI's API models (GPT-4o, GPT-4, o1, o3, etc.).

    Note: API-only (no local weights). Use LocalAdapter for local models.

    Config keys:
        api_key (str): OpenAI API key. Falls back to OPENAI_API_KEY env var.
        organization (str, optional): OpenAI organization ID.
        base_url (str, optional): Custom endpoint for proxies (e.g. OpenAI-compatible APIs).
        max_retries (int): Number of retries on failure.
        timeout (int): Request timeout in seconds.
    """

    name = "openai"
    provider = "openai"
    supported_types = [ModelType.TEXT]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._client = None

    def connect(self, config: Dict[str, Any]) -> None:
        _lazy_import()
        from openai import OpenAI
        import os

        api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key required. Set 'api_key' in config or OPENAI_API_KEY env var."
            )

        self._client = OpenAI(
            api_key=api_key,
            organization=config.get("organization"),
            base_url=config.get("base_url"),
            max_retries=config.get("max_retries", 3),
            timeout=config.get("timeout", 60),
        )
        log.info("OpenAI adapter connected (org: %s)", config.get("organization", "default"))

    def disconnect(self) -> None:
        self._client = None

    def get_model(self, model_id: str, **kwargs) -> Any:
        """Return a model wrapper that provides a consistent interface."""
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return _OpenAIModelWrapper(self._client, model_id, kwargs)

    def predict(self, model: Any, inputs: Any, **kwargs) -> Any:
        return model.predict(inputs, **kwargs)

    def get_input_spec(self, model: Any) -> Dict[str, Any]:
        return {"type": "text", "model_id": model.model_id}

    def supports_model_type(self, model_type: ModelType) -> bool:
        return model_type == ModelType.TEXT

    def tokenize(self, text: str, **kwargs) -> Dict[str, Any]:
        # OpenAI's API handles tokenization internally
        return {"prompt": text, **kwargs}

    def generate(self, model: Any, prompt: str, **kwargs) -> str:
        return model.predict({"prompt": prompt}, **kwargs)

    def get_logits(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError(
            "Logit extraction requires logprobs parameter. "
            "OpenAI API returns logprobs via the 'logprobs' argument."
        )

    def get_attention_weights(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError(
            "Attention weights are not available via OpenAI's API (black-box model)."
        )

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "api_key": {"type": "string"},
                "organization": {"type": "string"},
                "base_url": {"type": "string", "description": "Custom base URL (e.g. for proxies)"},
                "max_retries": {"type": "integer", "default": 3},
                "timeout": {"type": "integer", "default": 60},
            },
        }

    @classmethod
    def auto_config(cls) -> Dict[str, Any]:
        import os
        return {"api_key": os.environ.get("OPENAI_API_KEY")}


class _OpenAIModelWrapper:
    """Lightweight wrapper to make an OpenAI model look like a local model."""

    def __init__(self, client, model_id: str, kwargs: Dict[str, Any]):
        self._client = client
        self.model_id = model_id
        self._defaults = kwargs

    def predict(self, inputs: Dict[str, Any], **kwargs) -> Any:
        merged = {**self._defaults, **kwargs}
        messages = inputs.get("messages", [{"role": "user", "content": inputs.get("prompt", "")}])
        response = self._client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            **merged,
        )
        return response