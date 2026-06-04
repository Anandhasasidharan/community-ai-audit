"""
HuggingFace adapter — works with any model on the HuggingFace Hub or locally.
Supports text (LLMs, mask-filling), image, embedding, and multimodal models.
"""

from typing import Any, Dict, List, Optional
import logging

from community_ai_audit.core.interfaces import (
    TextModelAdapter,
    ImageModelAdapter,
    MultiModalAdapter,
    ModelType,
)

log = logging.getLogger(__name__)

torch = None
transformers = None
tokenizer_utils = None


def _lazy_import():
    global torch, transformers, tokenizer_utils
    if torch is None:
        import torch

        transformers = safe_import("transformers")
        if transformers is None:
            raise ImportError("transformers not installed. Run: pip install transformers torch")


def safe_import(name, package=None):
    import importlib

    try:
        return importlib.import_module(name, package=package)
    except ImportError:
        return None


class HuggingFaceAdapter(TextModelAdapter, ImageModelAdapter, MultiModalAdapter):
    """Adapter for HuggingFace models.

    Handles auto-detection of model type (text/image/multimodal) based on
    the model's config, and exposes a consistent interface for the audit framework.

    Config keys:
        token (str, optional): HF token for gated models.
        device (str): 'auto', 'cpu', 'cuda', 'mps'.
        torch_dtype (str): 'auto', 'float32', 'float16', 'bfloat16'.
        trust_remote_code (bool): Allow custom model code.
        cache_dir (str): Model cache location.
    """

    name = "huggingface"
    provider = "huggingface"
    supported_types = [ModelType.TEXT, ModelType.IMAGE, ModelType.MULTIMODAL, ModelType.EMBEDDING]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._tokenizer = None
        self._device = "cpu"
        self._model = None

    def connect(self, config: Dict[str, Any]) -> None:
        _lazy_import()
        self._device = self._resolve_device(self.config.get("device", "auto"))
        log.info("HuggingFace adapter connected (device: %s)", self._device)

    def disconnect(self) -> None:
        if self._model is not None:
            del self._model
            if torch and hasattr(torch, "cuda") and torch.cuda.is_available():
                torch.cuda.empty_cache()
        self._model = None
        self._tokenizer = None

    def get_model(self, model_id: str, **kwargs) -> Any:
        _lazy_import()
        from transformers import AutoModel, AutoProcessor
        import torch

        trust_remote = self.config.get("trust_remote_code", False)
        token = self.config.get("token")

        # Determine model class heuristically from config
        config_only = kwargs.get("config_only", False)
        if config_only:
            from transformers import AutoConfig

            return AutoConfig.from_pretrained(
                model_id,
                token=token,
                trust_remote_code=trust_remote,
            )

        dtype_str = self.config.get("torch_dtype", "auto")
        dtype = getattr(torch, dtype_str, torch.float32) if dtype_str != "auto" else "auto"

        device = kwargs.pop("device", self._device)
        use_safetensors = kwargs.pop("use_safetensors", True)

        model = AutoModel.from_pretrained(
            model_id,
            torch_dtype=dtype,
            device_map=device if device != "auto" else None,
            trust_remote_code=trust_remote,
            token=token,
            use_safetensors=use_safetensors,
            **kwargs,
        )

        self._model = model

        # Try loading tokenizer (text models)
        try:
            self._tokenizer = AutoProcessor.from_pretrained(
                model_id, token=token, trust_remote_code=trust_remote
            )
        except Exception:
            pass

        return model

    def predict(self, model: Any, inputs: Any, **kwargs) -> Any:
        import torch

        with torch.no_grad():
            return model(**inputs) if isinstance(inputs, dict) else model(inputs)

    def get_input_spec(self, model: Any) -> Dict[str, Any]:
        return {
            "type": "text",
            "device": str(self._device),
            "tokenizer": self._tokenizer,
            "model_name": getattr(model, "name_or_path", "unknown"),
        }

    def supports_model_type(self, model_type: ModelType) -> bool:
        return model_type in self.supported_types

    def tokenize(self, text: str, **kwargs) -> Any:
        if self._tokenizer is None:
            raise RuntimeError("No tokenizer loaded. Load a text model first.")
        return self._tokenizer(text, return_tensors="pt", **kwargs)

    def generate(self, model: Any, prompt: str, **kwargs) -> str:
        inputs = self.tokenize(prompt)
        if hasattr(inputs, "to"):
            inputs = {k: v.to(self._device) for k, v in inputs.items()}
        outputs = model.generate(**inputs, **kwargs)
        return self._tokenizer.decode(outputs[0], skip_special_tokens=True)

    def get_logits(self, model: Any, tokens: Any, **kwargs) -> Any:
        if hasattr(tokens, "to"):
            tokens = {k: v.to(self._device) for k, v in tokens.items()}
        out = model(**tokens)
        return out.logits if hasattr(out, "logits") else out[0]

    def get_attention_weights(self, model: Any, tokens: Any, **kwargs) -> Any:
        handles = []
        attention_weights = []

        def hook_fn(module, input, output):
            attn = output.attentions if hasattr(output, "attentions") else None
            if attn is not None:
                attention_weights.append(attn)

        for layer in model.model.layers if hasattr(model, "model") else model.transformer.h:
            handle = layer.register_forward_hook(hook_fn)
            handles.append(handle)

        try:
            if hasattr(tokens, "to"):
                tokens = {k: v.to(self._device) for k, v in tokens.items()}
            model(**tokens)
        finally:
            for h in handles:
                h.remove()

        return attention_weights

    def preprocess_image(self, image: Any, **kwargs) -> Any:
        if self._tokenizer is not None and hasattr(self._tokenizer, "image_processor"):
            return self._tokenizer.image_processor(image, return_tensors="pt")
        raise NotImplementedError("Image preprocessing requires a vision processor")

    def get_layer_activations(
        self, model: Any, image: Any, layer_names: List[str]
    ) -> Dict[str, Any]:
        import torch

        activations: Dict[str, Any] = {}

        def hook_fn(name):
            def fn(module, input, output):
                activations[name] = (
                    output.detach() if isinstance(output, torch.Tensor) else output[0].detach()
                )

            return fn

        handles = []
        for layer_name in layer_names:
            parts = layer_name.split(".")
            obj = model
            for part in parts:
                obj = getattr(obj, part)
            h = obj.register_forward_hook(hook_fn(layer_name))
            handles.append(h)

        try:
            model(image)
        finally:
            for h in handles:
                h.remove()

        return activations

    @staticmethod
    def _resolve_device(device: str) -> str:
        import torch

        if device == "auto":
            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            return "cpu"
        return device

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "token": {
                    "type": "string",
                    "description": "HuggingFace API token (optional for public models)",
                },
                "device": {"type": "string", "enum": ["auto", "cpu", "cuda", "mps"]},
                "torch_dtype": {
                    "type": "string",
                    "enum": ["auto", "float32", "float16", "bfloat16"],
                },
                "trust_remote_code": {"type": "boolean", "default": False},
                "cache_dir": {"type": "string"},
            },
        }

    @classmethod
    def auto_config(cls) -> Dict[str, Any]:
        import os

        return {"token": os.environ.get("HF_TOKEN")}
