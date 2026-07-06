"""
Replicate adapter — runs models on Replicate's cloud platform
via the Replicate Python API.
"""

from typing import Any, Dict, Optional
import logging

from community_ai_audit.core.interfaces import TextModelAdapter, ModelType

log = logging.getLogger(__name__)

replicate = None


def _lazy_import():
    global replicate
    if replicate is None:
        replicate = safe_import("replicate")
        if replicate is None:
            raise ImportError("replicate not installed. Run: pip install replicate")


def safe_import(name, package=None):
    import importlib

    try:
        return importlib.import_module(name, package=package)
    except ImportError:
        return None


class ReplicateAdapter(TextModelAdapter):
    """Adapter for Replicate's cloud model API.

    Config keys:
        api_token (str): Replicate API token. Falls back to REPLICATE_API_TOKEN env var.
        timeout (int): Prediction timeout in seconds. Default: 60.
    """

    name = "replicate"
    provider = "replicate"
    supported_types = [ModelType.TEXT, ModelType.IMAGE, ModelType.MULTIMODAL]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._client = None

    def connect(self, config: Dict[str, Any]) -> None:
        _lazy_import()
        import os

        api_token = config.get("api_token") or os.environ.get("REPLICATE_API_TOKEN")
        if not api_token:
            raise ValueError(
                "Replicate API token required. Set 'api_token' or REPLICATE_API_TOKEN."
            )

        os.environ["REPLICATE_API_TOKEN"] = api_token
        self._timeout = int(config.get("timeout", 60))
        self._client = replicate
        log.info("Replicate adapter connected")

    def disconnect(self) -> None:
        self._client = None

    def get_model(self, model_id: str, **kwargs) -> Any:
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return _ReplicateModelWrapper(self._client, model_id, self._timeout, kwargs)

    def predict(self, model: Any, inputs: Any, **kwargs) -> Any:
        return model.predict(inputs, **kwargs)

    def get_input_spec(self, model: Any) -> Dict[str, Any]:
        return {"type": "text", "model_id": model.model_id}

    def supports_model_type(self, model_type: ModelType) -> bool:
        return model_type in (ModelType.TEXT, ModelType.IMAGE, ModelType.MULTIMODAL)

    def tokenize(self, text: str, **kwargs) -> Dict[str, Any]:
        return {"input": {"prompt": text, **kwargs}}

    def generate(self, model: Any, prompt: str, **kwargs) -> str:
        result = model.predict({"prompt": prompt}, **kwargs)
        if isinstance(result, list):
            return "".join(result)
        return str(result)

    def get_logits(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError("Logits not available via Replicate API (black-box model).")

    def get_attention_weights(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError("Attention weights not available via Replicate API.")

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "api_token": {"type": "string"},
                "timeout": {"type": "integer", "default": 60},
            },
        }

    @classmethod
    def auto_config(cls) -> Dict[str, Any]:
        import os

        return {"api_token": os.environ.get("REPLICATE_API_TOKEN")}


class _ReplicateModelWrapper:
    """Wrapper for Replicate model predictions."""

    def __init__(self, client, model_id: str, timeout: int, kwargs: Dict[str, Any]):
        self._client = client
        self.model_id = model_id
        self._timeout = timeout
        self._defaults = kwargs

    def predict(self, inputs: Dict[str, Any], **kwargs) -> str:
        input_data = inputs.get("input", inputs)
        prediction = self._client.run(
            self.model_id,
            input=input_data,
        )
        if isinstance(prediction, list):
            return "".join(prediction)
        return str(prediction)
