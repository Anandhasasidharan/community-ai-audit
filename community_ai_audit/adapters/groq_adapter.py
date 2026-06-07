"""
Groq adapter — works with Groq's fast inference API
for open-source LLMs (Llama, Mixtral, Gemma, etc.).
"""

from typing import Any, Dict, Optional
import logging

from community_ai_audit.core.interfaces import TextModelAdapter, ModelType

log = logging.getLogger(__name__)

groq = None


def _lazy_import():
    global groq
    if groq is None:
        groq = safe_import("groq")
        if groq is None:
            raise ImportError("groq not installed. Run: pip install groq")


def safe_import(name, package=None):
    import importlib

    try:
        return importlib.import_module(name, package=package)
    except ImportError:
        return None


class GroqAdapter(TextModelAdapter):
    """Adapter for Groq's API models (Llama, Mixtral, Gemma, etc.).

    Config keys:
        api_key (str): Groq API key. Falls back to GROQ_API_KEY env var.
        base_url (str, optional): Custom endpoint.
        timeout (int): Request timeout in seconds. Default: 30.
    """

    name = "groq"
    provider = "groq"
    supported_types = [ModelType.TEXT]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._client = None

    def connect(self, config: Dict[str, Any]) -> None:
        _lazy_import()
        from groq import Groq
        import os

        api_key = config.get("api_key") or os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Groq API key required. Set 'api_key' or GROQ_API_KEY.")

        self._client = Groq(
            api_key=api_key,
            base_url=config.get("base_url"),
            timeout=config.get("timeout", 30),
        )
        log.info("Groq adapter connected")

    def disconnect(self) -> None:
        self._client = None

    def get_model(self, model_id: str, **kwargs) -> Any:
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return _GroqModelWrapper(self._client, model_id, kwargs)

    def predict(self, model: Any, inputs: Any, **kwargs) -> Any:
        return model.predict(inputs, **kwargs)

    def get_input_spec(self, model: Any) -> Dict[str, Any]:
        return {"type": "text", "model_id": model.model_id}

    def supports_model_type(self, model_type: ModelType) -> bool:
        return model_type == ModelType.TEXT

    def tokenize(self, text: str, **kwargs) -> Dict[str, Any]:
        return {"prompt": text, **kwargs}

    def generate(self, model: Any, prompt: str, **kwargs) -> str:
        return model.predict({"prompt": prompt}, **kwargs)

    def get_logits(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError("Logits not available via Groq API (black-box model).")

    def get_attention_weights(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError("Attention weights not available via Groq API.")

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "api_key": {"type": "string"},
                "base_url": {"type": "string", "description": "Custom base URL"},
                "timeout": {"type": "integer", "default": 30},
            },
        }

    @classmethod
    def auto_config(cls) -> Dict[str, Any]:
        import os

        return {"api_key": os.environ.get("GROQ_API_KEY")}


class _GroqModelWrapper:
    """Lightweight wrapper for Groq API models."""

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
