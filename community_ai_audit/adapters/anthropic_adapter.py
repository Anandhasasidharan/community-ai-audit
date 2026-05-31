"""
Anthropic adapter — works with Claude models via the Anthropic API.
"""

from typing import Any, Dict, Optional
import logging

from community_ai_audit.core.interfaces import ModelAdapter, TextModelAdapter, ModelType

log = logging.getLogger(__name__)


def safe_import(name, package=None):
    import importlib
    try:
        return importlib.import_module(name, package=package)
    except ImportError:
        return None


class AnthropicAdapter(TextModelAdapter):
    """Adapter for Anthropic Claude models via the official API.

    Config keys:
        api_key (str): Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
        base_url (str, optional): Custom endpoint.
        max_retries (int): Number of retries.
        timeout (int): Request timeout in seconds.
    """

    name = "anthropic"
    provider = "anthropic"
    supported_types = [ModelType.TEXT]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._client = None

    def connect(self, config: Dict[str, Any]) -> None:
        anthropic = safe_import("anthropic")
        if anthropic is None:
            raise ImportError("anthropic not installed. Run: pip install anthropic")
        import os
        api_key = config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key required. Set 'api_key' or ANTHROPIC_API_KEY env var.")

        anthropic_version = safe_import("anthropic").__version__  # type: ignore
        if anthropic_version and anthropic_version.startswith("0."):
            # Anthropic Python SDK v0.x
            self._client = anthropic.Anthropic(api_key=api_key)  # type: ignore
        else:
            # Anthropic Python SDK v1.x
            from anthropic import Anthropic
            self._client = Anthropic(api_key=api_key)

        log.info("Anthropic adapter connected")

    def disconnect(self) -> None:
        self._client = None

    def get_model(self, model_id: str, **kwargs) -> Any:
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return _ClaudeModelWrapper(self._client, model_id, kwargs)

    def predict(self, model: Any, inputs: Any, **kwargs) -> Any:
        return model.predict(inputs, **kwargs)

    def get_input_spec(self, model: Any) -> Dict[str, Any]:
        return {"type": "text", "model_id": model.model_id}

    def supports_model_type(self, model_type: ModelType) -> bool:
        return model_type == ModelType.TEXT

    def tokenize(self, text: str, **kwargs) -> Dict[str, Any]:
        return {"prompt": text}

    def generate(self, model: Any, prompt: str, **kwargs) -> str:
        return model.predict({"prompt": prompt}, **kwargs)

    def get_logits(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError("Logits not available via Anthropic API (black-box).")

    def get_attention_weights(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError("Attention weights not available via Anthropic API (black-box).")

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "api_key": {"type": "string"},
                "base_url": {"type": "string"},
                "max_retries": {"type": "integer", "default": 3},
                "timeout": {"type": "integer", "default": 60},
            },
        }

    @classmethod
    def auto_config(cls) -> Dict[str, Any]:
        import os
        return {"api_key": os.environ.get("ANTHROPIC_API_KEY")}


class _ClaudeModelWrapper:
    def __init__(self, client, model_id: str, kwargs: Dict[str, Any]):
        self._client = client
        self.model_id = model_id
        self._defaults = kwargs

    def predict(self, inputs: Dict[str, Any], **kwargs) -> Any:
        merged = {**self._defaults, **kwargs}
        # v0.x vs v1.x SDK compatibility
        if hasattr(self._client, "messages"):
            return self._client.messages.create(
                model=self.model_id,
                messages=[{"role": "user", "content": inputs.get("prompt", "")}],
                **merged,
            )
        else:
            return self._client.completions.create(
                model=self.model_id,
                prompt=inputs.get("prompt", ""),
                **merged,
            )