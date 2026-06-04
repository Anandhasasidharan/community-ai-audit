# Adding a New Model Adapter — Step-by-Step

> **Time to complete:** ~30 minutes
> **Goal:** Add support for a new model provider (e.g., Cohere, Mistral, or a custom inference server).

## 1. Understand the Interface

The `ModelAdapter` ABC requires these methods:

| Method | Purpose |
|--------|---------|
| `connect(config)` | Initialize connection (API keys, endpoints) |
| `disconnect()` | Clean up |
| `get_model(model_id, **kwargs)` | Load/retrieve the model |
| `predict(model, inputs, **kwargs)` | Run inference |
| `get_input_spec(model)` | Return input shape, dtype, tokenizer info |
| `supports_model_type(model_type)` | Check if adapter handles text/image/multimodal |

For text models, also implement `TextModelAdapter` which adds `tokenize()`, `generate()`, `get_logits()`, and `get_attention_weights()`.

## 2. Create Your Adapter File

Create `community_ai_audit/adapters/my_provider_adapter.py`:

```python
"""Adapter for MyProvider API."""

from typing import Any, Dict
from community_ai_audit.core.interfaces import TextModelAdapter, ModelType

class MyProviderAdapter(TextModelAdapter):
    name = "myprovider"
    provider = "myprovider"
    supported_types = [ModelType.TEXT]

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._client = None

    def connect(self, config: Dict[str, Any]) -> None:
        import os
        api_key = config.get("api_key") or os.environ.get("MYPROVIDER_API_KEY")
        if not api_key:
            raise ValueError("Set 'api_key' or MYPROVIDER_API_KEY")
        self._client = {"api_key": api_key}  # Replace with real client init

    def disconnect(self) -> None:
        self._client = None

    def get_model(self, model_id: str, **kwargs) -> Any:
        return {"model_id": model_id, "client": self._client}

    def predict(self, model: Any, inputs: Any, **kwargs) -> Any:
        # Run inference, return raw outputs (logits, embeddings, etc.)
        raise NotImplementedError("Implement predict()")

    def get_input_spec(self, model: Any) -> Dict[str, Any]:
        return {"type": "text", "shape": "(batch, seq)", "tokenizer": "auto"}

    def supports_model_type(self, model_type: ModelType) -> bool:
        return model_type in self.supported_types

    def tokenize(self, text: str, **kwargs) -> Any:
        return text.split()  # Replace with real tokenizer

    def generate(self, model: Any, prompt: str, **kwargs) -> str:
        raise NotImplementedError("Implement generate()")

    intu
    def get_logits(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError("Implement get_logits()")

    def get_attention_weights(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError("Implement get_attention_weights()")
```

## 3. Register Your Adapter

Add to `community_ai_audit/adapters/__init__.py`:

```python
from .my_provider_adapter import MyProviderAdapter

__all__.append("MyProviderAdapter")
```

Or register dynamically in `community_ai_audit/adapters/registry.py`:

```python
from .my_provider_adapter import MyProviderAdapter
registry = AdapterRegistry()
registry.register("myprovider", MyProviderAdapter)
```

## 4. Test Your Adapter

```python
from community_ai_audit.core.audit import AuditEngine

engine = AuditEngine()
engine.load_model("my-model-id", provider="myprovider", adapter_config={"api_key": "test-key"})
```

## 5. Verify Discovery

```bash
python -m community_ai_audit.cli discover
```

You should see `myprovider` in the adapter list.

## Full Working Example

See `examples/minimal_adapter.py` for a complete minimal adapter that wraps a dummy HTTP API.
