"""
Vertex AI adapter — works with Google Vertex AI (Gemini models) via the official SDK.
"""

from typing import Any, Dict, Optional
import logging

from community_ai_audit.core.interfaces import TextModelAdapter, ModelType

log = logging.getLogger(__name__)

vertexai = None
genai = None


def _lazy_import():
    global vertexai, genai
    if vertexai is None:
        vertexai = safe_import("vertexai")
        if vertexai is None:
            raise ImportError("vertexai not installed. Run: pip install google-cloud-aiplatform")
    if genai is None:
        genai = safe_import("vertexai.generative_models")
        if genai is None:
            raise ImportError(
                "vertexai.generative_models not available. Run: pip install google-cloud-aiplatform"
            )


def safe_import(name, package=None):
    import importlib

    try:
        return importlib.import_module(name, package=package)
    except ImportError:
        return None


class VertexAIAdapter(TextModelAdapter):
    """Adapter for Google Vertex AI models (Gemini Pro, Gemini Ultra, etc.).

    Note: API-only (no local weights). Use LocalAdapter for local models.

    Config keys:
        project_id (str): GCP project ID. Falls back to VERTEXAI_PROJECT_ID env var.
        location (str): GCP location (e.g. us-central1). Falls back to VERTEXAI_LOCATION env var.
        model_name (str): Vertex AI model name (e.g. 'gemini-1.5-pro'). Default: 'gemini-1.5-pro'.
    """

    name = "vertexai"
    provider = "vertexai"
    supported_types = [ModelType.TEXT, ModelType.MULTIMODAL]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._client = None

    def connect(self, config: Dict[str, Any]) -> None:
        _lazy_import()
        import os

        project_id = config.get("project_id") or os.environ.get("VERTEXAI_PROJECT_ID")
        location = config.get("location") or os.environ.get("VERTEXAI_LOCATION", "us-central1")
        model_name = config.get("model_name", "gemini-1.5-pro")

        if not project_id:
            raise ValueError(
                "Vertex AI project_id required. Set 'project_id' in config or VERTEXAI_PROJECT_ID env var."
            )

        vertexai.init(project=project_id, location=location)
        self._client = genai.GenerativeModel(model_name)
        log.info(
            "Vertex AI adapter connected (project: %s, location: %s, model: %s)",
            project_id,
            location,
            model_name,
        )

    def disconnect(self) -> None:
        self._client = None

    def get_model(self, model_id: str, **kwargs) -> Any:
        """Return a model wrapper that provides a consistent interface."""
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return _VertexAIModelWrapper(self._client, model_id, kwargs)

    def predict(self, model: Any, inputs: Any, **kwargs) -> Any:
        return model.predict(inputs, **kwargs)

    def get_input_spec(self, model: Any) -> Dict[str, Any]:
        return {"type": "text"}

    def supports_model_type(self, model_type: ModelType) -> bool:
        return model_type in [ModelType.TEXT, ModelType.MULTIMODAL]

    def tokenize(self, text: str, **kwargs) -> Dict[str, Any]:
        # Vertex AI handles tokenization internally
        return {"prompt": text, **kwargs}

    def generate(self, model: Any, prompt: str, **kwargs) -> str:
        return model.predict({"prompt": prompt}, **kwargs)

    def get_logits(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError(
            "Logit extraction is not supported via Vertex AI's API (black-box API)."
        )

    def get_attention_weights(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError(
            "Attention weights are not available via Vertex AI's API (black-box API)."
        )

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "GCP project ID"},
                "location": {
                    "type": "string",
                    "description": "GCP location (e.g. us-central1)",
                    "default": "us-central1",
                },
                "model_name": {
                    "type": "string",
                    "description": "Vertex AI model name (e.g. gemini-1.5-pro)",
                    "default": "gemini-1.5-pro",
                },
            },
        }

    @classmethod
    def auto_config(cls) -> Dict[str, Any]:
        import os

        return {
            "project_id": os.environ.get("VERTEXAI_PROJECT_ID"),
            "location": os.environ.get("VERTEXAI_LOCATION", "us-central1"),
        }


class _VertexAIModelWrapper:
    """Lightweight wrapper to make a Vertex AI GenerativeModel look like a local model."""

    def __init__(self, client, model_id: str, kwargs: Dict[str, Any]):
        self._client = client
        self.model_id = model_id
        self._defaults = kwargs

    def predict(self, inputs: Dict[str, Any], **kwargs) -> Any:
        merged = {**self._defaults, **kwargs}
        prompt = inputs.get("prompt", "")
        response = self._client.generate_content(prompt, **merged)
        return response
