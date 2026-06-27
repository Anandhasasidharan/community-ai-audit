"""
Integrated Gradients interpreter.
Practical implementation for white-box torch models.
"""

from typing import Any, Dict, Optional
import logging

from community_ai_audit.core.interfaces import (
    InterpreterPlugin,
    InterpretationResult,
    ModelAdapter,
)
from community_ai_audit.adapters.base import is_text_model, get_model_device

log = logging.getLogger(__name__)


class IntegratedGradientsInterpreter(InterpreterPlugin):
    name = "integrated-gradients"
    description = "Feature attribution via path-integrated gradients"
    version = "0.2.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def interpret(
        self,
        model: Any,
        adapter: ModelAdapter,
        inputs: Any,
        target: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> InterpretationResult:
        cfg = {**self.config, **(config or {})}
        steps = int(cfg.get("steps", 50))
        baseline_mode = cfg.get("baseline", "zero")

        if not self._can_compute_gradients(adapter, model):
            return InterpretationResult(
                interpreter_name=self.name,
                interpreter_version=self.version,
                error="Integrated Gradients requires white-box gradient access.",
            )

        if is_text_model(model):
            return InterpretationResult(
                interpreter_name=self.name,
                interpreter_version=self.version,
                error=(
                    "Integrated Gradients on token IDs (discrete) is not supported for text models. "
                    "IG requires differentiable inputs; for text models, use embedding-space IG "
                    "which requires access to the model's input embeddings layer."
                ),
            )

        try:

            x = self._to_tensor_input(inputs, device=get_model_device(model), model=model)
            if x is None:
                return InterpretationResult(
                    interpreter_name=self.name,
                    interpreter_version=self.version,
                    error=(
                        "Unsupported input format for Integrated Gradients. "
                        "Pass a numeric tensor/list (e.g. --input '[0.1, 0.2, ...]')."
                    ),
                )

            if x.dim() == 1:
                x = x.unsqueeze(0)

            baseline = self._build_baseline(x, mode=baseline_mode, model=model)
            target_idx = self._resolve_target(model, x, target)
            attributions = self._integrated_gradients(model, x, baseline, target_idx, steps)

            summary = self._summarize(attributions)
            return InterpretationResult(
                interpreter_name=self.name,
                interpreter_version=self.version,
                attributions={"integrated_gradients": attributions.detach().cpu().tolist()},
                summary=summary,
                metadata={
                    "steps": steps,
                    "baseline": baseline_mode,
                    "target_index": int(target_idx),
                },
            )

        except Exception as e:
            log.exception("Integrated gradients failed")
            return InterpretationResult(
                interpreter_name=self.name,
                interpreter_version=self.version,
                error=str(e),
            )

    def _to_tensor_input(self, inputs: Any, device, model=None):
        import torch

        text_model = model is not None and is_text_model(model)

        if isinstance(inputs, torch.Tensor):
            if text_model and inputs.dtype.is_floating_point:
                return inputs.detach().clone().to(device).long()
            return inputs.detach().clone().to(device).float()

        if isinstance(inputs, (list, tuple)):
            if text_model and inputs and isinstance(inputs[0], int):
                return torch.tensor(inputs, dtype=torch.long, device=device)
            return torch.tensor(inputs, dtype=torch.float32, device=device)

        if isinstance(inputs, dict):
            if "tensor" in inputs:
                tensor_data = inputs["tensor"]
                if (
                    text_model
                    and isinstance(tensor_data, (list, tuple))
                    and tensor_data
                    and isinstance(tensor_data[0], int)
                ):
                    return torch.tensor(tensor_data, dtype=torch.long, device=device)
                return torch.tensor(tensor_data, dtype=torch.float32, device=device)
            if "input" in inputs and isinstance(inputs["input"], (list, tuple)):
                input_data = inputs["input"]
                if text_model and input_data and isinstance(input_data[0], int):
                    return torch.tensor(input_data, dtype=torch.long, device=device)
                return torch.tensor(input_data, dtype=torch.float32, device=device)

        return None

    def _build_baseline(self, x, mode: str, model=None):
        import torch

        text_model = model is not None and is_text_model(model)

        if text_model:
            # For text models, use padding token (0) or special token as baseline
            if mode == "random":
                # Random tokens near padding
                return torch.randint(0, 10, x.shape, device=x.device, dtype=torch.long)
            if mode == "mean":
                return torch.full_like(x, 0, dtype=torch.long)
            # zero baseline default = padding token
            return torch.zeros_like(x, dtype=torch.long)

        if mode == "random":
            return torch.randn_like(x) * 0.01
        if mode == "mean":
            return torch.full_like(x, float(x.mean().item()))
        # zero baseline default
        return torch.zeros_like(x)

    def _resolve_target(self, model: Any, x, target: Optional[Any]) -> int:
        import torch

        if target is not None:
            return int(target)
        with torch.no_grad():
            logits = self._forward_logits(model, x)
            if logits.dim() == 1:
                return int(torch.argmax(logits).item())
            return int(torch.argmax(logits[0]).item())

    def _forward_logits(self, model: Any, x):
        out = model(x)
        if isinstance(out, tuple):
            out = out[0]
        if hasattr(out, "logits"):
            return out.logits
        return out

    def _integrated_gradients(self, model: Any, x, baseline, target_idx: int, steps: int):
        import torch

        total_grads = torch.zeros_like(x)
        delta = x - baseline

        for i in range(1, steps + 1):
            alpha = float(i) / float(steps)
            scaled = (baseline + alpha * delta).detach().requires_grad_(True)
            logits = self._forward_logits(model, scaled)
            if logits.dim() == 1:
                target_val = logits[target_idx]
            else:
                target_val = logits[:, target_idx].sum()

            model.zero_grad(set_to_none=True)
            if scaled.grad is not None:
                scaled.grad.zero_()
            target_val.backward()
            grads = scaled.grad.detach()
            total_grads += grads

        avg_grads = total_grads / float(steps)
        return delta * avg_grads

    def _summarize(self, attributions) -> str:
        import torch

        abs_attr = attributions.abs().flatten()
        mean_mag = float(abs_attr.mean().item())
        max_mag = float(abs_attr.max().item())
        top_idx = int(torch.argmax(abs_attr).item()) if abs_attr.numel() > 0 else -1
        return f"Mean abs attribution: {mean_mag:.6f}; max: {max_mag:.6f}; top feature index: {top_idx}."

    def _can_compute_gradients(self, adapter: ModelAdapter, model: Any) -> bool:
        provider = getattr(adapter, "provider", "unknown")
        if provider in {"openai", "anthropic", "aws"}:
            return False
        return hasattr(model, "parameters")
