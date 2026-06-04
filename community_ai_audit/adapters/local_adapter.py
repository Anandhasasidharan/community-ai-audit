"""
Local adapter — works with locally stored models.
Supports PyTorch (.pt, .pth), SafeTensors (.safetensors), ONNX (.onnx),
and directory-based model formats (HuggingFace local, FastAI, etc.).
"""

from typing import Any, Dict, Optional
from pathlib import Path
import logging

from community_ai_audit.core.interfaces import ModelAdapter, ModelType

log = logging.getLogger(__name__)


def safe_import(name, package=None):
    import importlib

    try:
        return importlib.import_module(name, package=package)
    except ImportError:
        return None


class LocalAdapter(ModelAdapter):
    """Adapter for locally stored model files and directories.

    Auto-detects format from file extension or directory structure.

    Supported formats:
        - .pt, .pth       → PyTorch checkpoint
        - .safetensors   → HuggingFace SafeTensors
        - .onnx          → ONNX model
        - Directory      → Auto-detect (HuggingFace format, FastAI, etc.)

    Config keys:
        device (str): 'auto', 'cpu', 'cuda', 'mps'.
        torch_dtype (str): 'auto', 'float32', 'float16', 'bfloat16'.
        load_in_8bit (bool): Quantize to 8-bit on load (bitsandbytes).
    """

    name = "local"
    provider = "local"
    supported_types = [ModelType.TEXT, ModelType.IMAGE, ModelType.MULTIMODAL, ModelType.EMBEDDING]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._device = "cpu"
        self._model = None
        self._tokenizer = None

    def connect(self, config: Dict[str, Any]) -> None:
        torch = safe_import("torch")
        if torch is None:
            raise ImportError("torch not installed. Run: pip install torch")
        self._device = self._resolve_device(config.get("device", "auto"))
        log.info("Local adapter connected (device: %s)", self._device)

    def disconnect(self) -> None:
        if self._model is not None:
            del self._model
            torch = safe_import("torch")
            if torch and hasattr(torch.cuda, "empty_cache"):
                torch.cuda.empty_cache()
        self._model = None
        self._tokenizer = None

    def get_model(self, model_id: str, **kwargs) -> Any:
        """Load a local model. model_id can be a file path or directory."""
        p = Path(model_id).expanduser()

        if not p.exists():
            raise FileNotFoundError(f"Model not found: {p}")

        if p.is_dir():
            return self._load_from_directory(p, **kwargs)
        elif p.suffix in (".pt", ".pth"):
            return self._load_pytorch(p, **kwargs)
        elif p.suffix == ".safetensors":
            return self._load_safetensors(p, **kwargs)
        elif p.suffix == ".onnx":
            return self._load_onnx(p, **kwargs)
        else:
            raise ValueError(f"Unsupported model format: {p.suffix}")

    def _load_from_directory(self, path: Path, **kwargs) -> Any:
        """Auto-detect format from directory structure."""
        # Check for HuggingFace format
        if (path / "config.json").exists() or (path / "model.safetensors").exists():
            return self._load_huggingface_local(path, **kwargs)
        # Check for FastAI format
        if (path / "export.pkl").exists():
            return self._load_fastai(path, **kwargs)
        raise ValueError(f"Could not auto-detect model format in directory: {path}")

    def _load_huggingface_local(self, path: Path, **kwargs) -> Any:
        _lazy_import("transformers")
        from transformers import AutoModel, AutoProcessor
        import torch

        dtype_str = self.config.get("torch_dtype", "auto")
        dtype = getattr(torch, dtype_str, torch.float32) if dtype_str != "auto" else "auto"

        model = AutoModel.from_pretrained(
            str(path),
            torch_dtype=dtype,
            device_map=kwargs.get("device", self._device),
            **kwargs,
        )
        self._model = model

        # Try loading processor
        try:
            self._tokenizer = AutoProcessor.from_pretrained(str(path))
        except Exception:
            pass

        return model

    def _load_pytorch(self, path: Path, **kwargs) -> Any:
        torch = safe_import("torch")
        if torch is None:
            raise ImportError("torch not installed")
        device = kwargs.get("device", self._device)
        weights_only = kwargs.get("weights_only", False)
        obj = torch.load(path, map_location=device, weights_only=weights_only)
        if (
            isinstance(obj, dict)
            and "state_dict" in obj
            and not kwargs.get("allow_state_dict", False)
        ):
            raise ValueError(
                "Loaded checkpoint contains only a state_dict. "
                "Provide a full model file, or pass allow_state_dict=True and reconstruct architecture manually."
            )
        return obj

    def _load_safetensors(self, path: Path, **kwargs) -> Any:
        safetensors = safe_import("safetensors")
        if safetensors is None:
            raise ImportError("safetensors not installed. Run: pip install safetensors")
        from safetensors.torch import load_file

        tensors = load_file(str(path), device=self._device)
        # Return as a dict (not a model) — caller needs to know the architecture
        return tensors

    def _load_onnx(self, path: Path, **kwargs) -> Any:
        onnxruntime = safe_import("onnxruntime")
        if onnxruntime is None:
            raise ImportError("onnxruntime not installed. Run: pip install onnxruntime")
        sess_options = onnxruntime.SessionOptions()
        return onnxruntime.InferenceSession(str(path), sess_options, **kwargs)

    def _load_fastai(self, path: Path, **kwargs) -> Any:
        fastai = safe_import("fastai")
        if fastai is None:
            raise ImportError("fastai not installed. Run: pip install fastai")
        from fastai.learner import load_learner

        return load_learner(path / "export.pkl")

    def predict(self, model: Any, inputs: Any, **kwargs) -> Any:
        if isinstance(model, dict):
            raise ValueError("SafeTensors loaded as tensor dict — requires architecture info.")
        if hasattr(model, "eval"):
            model.eval()
        if isinstance(inputs, dict):
            return model(**inputs)
        return model(inputs)

    def get_input_spec(self, model: Any) -> Dict[str, Any]:
        return {
            "type": "local",
            "path": str(getattr(model, "model_dir", "unknown")),
            "device": self._device,
            "tokenizer": self._tokenizer,
        }

    def supports_model_type(self, model_type: ModelType) -> bool:
        return model_type in self.supported_types

    def tokenize(self, text: str, **kwargs) -> Any:
        if self._tokenizer is None:
            raise RuntimeError("No tokenizer loaded. Use a text model directory.")
        return self._tokenizer(text, return_tensors="pt")

    def generate(self, model: Any, prompt: str, **kwargs) -> str:
        if hasattr(model, "generate"):
            inputs = self.tokenize(prompt)
            outputs = model.generate(**inputs)
            return self._tokenizer.decode(outputs[0])
        raise NotImplementedError("generate() requires a model with .generate() method")

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "device": {"type": "string", "enum": ["auto", "cpu", "cuda", "mps"]},
                "torch_dtype": {
                    "type": "string",
                    "enum": ["auto", "float32", "float16", "bfloat16"],
                },
                "load_in_8bit": {"type": "boolean"},
            },
        }

    @classmethod
    def auto_config(cls) -> Dict[str, Any]:
        import torch

        return {"device": "cuda" if torch.cuda.is_available() else "cpu"}

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


def _lazy_import(module_name: str):
    import importlib

    try:
        importlib.import_module(module_name)
    except ImportError:
        raise ImportError(f"{module_name} not installed")
