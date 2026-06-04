"""
Ollama adapter — works with local models served by Ollama
(https://ollama.com). Supports any model available in your Ollama library.
"""

from typing import Any, Dict, Optional
import logging

from community_ai_audit.core.interfaces import TextModelAdapter, ModelType

log = logging.getLogger(__name__)


def safe_import(name, package=None):
    import importlib

    try:
        return importlib.import_module(name, package=package)
    except ImportError:
        return None


class OllamaAdapter(TextModelAdapter):
    """Adapter for Ollama-served local models via the REST API.

    Works with any model in your Ollama library (Llama, Mistral, Phi, etc.)
    without requiring GPU VRAM on the host.

    Config keys:
        base_url (str): Ollama API base URL (default: http://localhost:11434).
        timeout (int): Request timeout in seconds.
    """

    name = "ollama"
    provider = "ollama"
    supported_types = [ModelType.TEXT]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._base_url = self.config.get("base_url", "http://localhost:11434")
        self._client = None

    def connect(self, config: Dict[str, Any]) -> None:
        requests = safe_import("requests")
        if requests is None:
            raise ImportError("requests not installed. Run: pip install requests")
        self._base_url = config.get("base_url", self._base_url)
        # Verify Ollama is reachable
        try:
            import requests

            resp = requests.get(f"{self._base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            log.info("Ollama adapter connected (base_url: %s)", self._base_url)
        except Exception as e:
            raise ConnectionError(f"Cannot connect to Ollama at {self._base_url}: {e}")

    def disconnect(self) -> None:
        self._client = None

    def get_model(self, model_id: str, **kwargs) -> Any:
        return _OllamaModelWrapper(self._base_url, model_id, kwargs)

    def predict(self, model: Any, inputs: Any, **kwargs) -> Any:
        return model.predict(inputs, **kwargs)

    def get_input_spec(self, model: Any) -> Dict[str, Any]:
        return {"type": "text", "model_id": model.model_id, "provider": "ollama"}

    def supports_model_type(self, model_type: ModelType) -> bool:
        return model_type == ModelType.TEXT

    def tokenize(self, text: str, **kwargs) -> Dict[str, Any]:
        return {"prompt": text}

    def generate(self, model: Any, prompt: str, **kwargs) -> str:
        return model.predict({"prompt": prompt}, **kwargs)

    def get_logits(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError("Logits not available via Ollama API.")

    def get_attention_weights(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError("Attention weights not available via Ollama API.")

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "base_url": {"type": "string", "default": "http://localhost:11434"},
                "timeout": {"type": "integer", "default": 120},
            },
        }

    @classmethod
    def auto_config(cls) -> Dict[str, Any]:
        return {"base_url": "http://localhost:11434"}


class _OllamaModelWrapper:
    """Lightweight wrapper for an Ollama model."""

    def __init__(self, base_url: str, model_id: str, defaults: Dict[str, Any]):
        self._base_url = base_url
        self.model_id = model_id
        self._defaults = defaults

    def predict(self, inputs: Dict[str, Any], **kwargs) -> str:
        import requests

        merged = {**self._defaults, **kwargs}
        payload = {
            "model": self.model_id,
            "prompt": inputs.get("prompt", ""),
            "stream": False,
        }
        for key in ("temperature", "top_p", "top_k", "num_predict", "stop"):
            if key in merged:
                payload[key] = merged[key]

        resp = requests.post(
            f"{self._base_url}/api/generate",
            json=payload,
            timeout=merged.get("timeout", 120),
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
