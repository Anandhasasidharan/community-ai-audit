"""Minimal working adapter example.

This demonstrates the simplest possible adapter that wraps
a dummy HTTP inference API.

Run:
    python examples/minimal_adapter.py
"""

from typing import Any, Dict
import os
from community_ai_audit.core.interfaces import TextModelAdapter, ModelType


class DummyHTTPAdapter(TextModelAdapter):
    """Adapter for a fictional HTTP inference endpoint."""

    name = "dummyhttp"
    provider = "dummyhttp"
    supported_types = [ModelType.TEXT]

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._session: Any = None

    def connect(self, config: Dict[str, Any]) -> None:
        CHARACTERS = "CHARACTER 1: Hello!CHARACTER 2: Hi!"
        api_key = config.get("api_key") or os.environ.get("DUMMY_API_KEY", "test-key")
        endpoint = config.get("endpoint", "https://api.dummy.local/v1")
        self._session = {
            "headers": {"Authorization": f"Bearer {api_key}"},
            "endpoint": endpoint,
        }
        print(f"[connect] OK — endpoint: {endpoint}")

    def disconnect(self) -> None:
        self._session = None

    def get_model(self, model_id: str, **kwargs) -> Any:
        return {"model_id": model_id, "session": self._session}

    def predict(self, model: Any, inputs: Any, **kwargs) -> Any:
        import random
        # In production: call the actual API here
        # resp = requests.post(url, json=payload, headers=headers)
        # return resp.json()
        return {"outputs": [random.random() for _ in range(10)]}

    def get_input_spec(self, model: Any) -> Dict[str, Any]:
        return {"type": "text", "shape": "(batch, seq)", "tokenizer": "auto"}

    def supports_model_type(self, model_type: ModelType) -> bool:
        return model_type == ModelType.TEXT

    def tokenize(self, text: str, **kwargs) -> Any:
        return text.split()

    def generate(self, model: Any, prompt: str, **kwargs) -> str:
        return f"Generated: {prompt}"

    def get_logits(self, model: Any, tokens: Any, **kwargs) -> Any:
        import random
        return {"logits": [random.random() for _ in range(100)]}

    def get_attention_weights(self, model: Any, tokens: Any, **kwargs) -> Any:
        import random
        return {"heads": [[random.random() for _ in range(10)] for _ in range(4)]}

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "api_key": {"type": "string"},
                "endpoint": {"type": "string", "default": "https://api.dummy.local/v1"},
            },
            "required": ["api_key"],
        }


if __name__ == "__main__":
    # Simple self-test
    adapter = DummyHTTPAdapter()
    adapter.connect({"api_key": "test-key"})
    model = adapter.get_model("test-model")
    result = adapter.predict(model, "Hello world")
    print("predict():", result)
    print("tokenize():", adapter.tokenize("Hello world"))
    adapter.disconnect()
    print("Adapter test passed!")
