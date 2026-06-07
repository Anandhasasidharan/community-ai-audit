"""
Adversarial vulnerability scanner.
Evaluates robustness against FGSM/PGD for white-box torch models.
"""

from typing import Any, Dict, Optional
import logging

from community_ai_audit.core.interfaces import (
    ScannerPlugin,
    Finding,
    ScanResult,
    Severity,
    ModelAdapter,
)

log = logging.getLogger(__name__)


class AdversarialScanner(ScannerPlugin):
    """Measures model resilience to gradient-based perturbations.

    This scanner is intentionally practical for MVP:
    - Runs on local/white-box torch models
    - Generates synthetic inputs when no dataset is provided
    - Reports attack success rate (pred changed after perturbation)
    """

    name = "adversarial"
    description = "Assessment of adversarial robustness (FGSM, PGD-based)"
    version = "0.2.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def scan(
        self, model: Any, adapter: ModelAdapter, config: Optional[Dict[str, Any]] = None
    ) -> ScanResult:
        cfg = {**self.config, **(config or {})}
        epsilon = float(cfg.get("epsilon", 0.1))
        alpha = float(cfg.get("alpha", 0.01))
        pgd_steps = int(cfg.get("pgd_steps", 10))
        num_samples = int(cfg.get("num_samples", 32))

        if not self._supports_gradients(adapter, model):
            return ScanResult(
                scanner_name=self.name,
                scanner_version=self.version,
                findings=[
                    Finding(
                        title="Adversarial scan limited: black-box model",
                        description=(
                            "This adapter/model does not expose gradients; "
                            "FGSM/PGD requires white-box access."
                        ),
                        severity=Severity.INFO,
                        confidence=0.6,
                        recommendation="Run this scanner with local/white-box models.",
                    )
                ],
            )

        # Check if model is a text/language model - adversarial attacks on token IDs don't work
        is_text_model = (
            hasattr(model.config, "vocab_size")
            or hasattr(model, "vocab_size")
            or hasattr(model, "wte")  # GPT-2 style
        )

        if is_text_model:
            return ScanResult(
                scanner_name=self.name,
                scanner_version=self.version,
                findings=[
                    Finding(
                        title="Adversarial scan limited: text model requires embedding-space attacks",
                        description=(
                            "FGSM/PGD on token IDs (discrete) is not supported. "
                            "Adversarial attacks on text models require embedding-space perturbations "
                            "which need access to the model's input embeddings layer."
                        ),
                        severity=Severity.INFO,
                        confidence=0.7,
                        mitre_id="AI-A1002",
                        recommendation=(
                            "For text model adversarial robustness, consider using "
                            "embedding-space attacks or discrete optimization methods "
                            "(e.g., HotFlip, TextFooler, BERT-Attack)."
                        ),
                    )
                ],
            )

        try:
            import torch

            device = self._get_device(model)
            x = self._build_probe_batch(
                model, cfg, num_samples=num_samples, device=device, adapter=adapter
            )
            if x is None:
                return ScanResult(
                    scanner_name=self.name,
                    scanner_version=self.version,
                    findings=[
                        Finding(
                            title="Adversarial scan could not create probe inputs",
                            description="Provide `input_shape` in scanner config (e.g. [32, 16]).",
                            severity=Severity.LOW,
                            confidence=0.3,
                            recommendation="Set scanners.adversarial.input_shape in config/default.yaml.",
                        )
                    ],
                )

            model.eval()
            with torch.no_grad():
                clean_logits = self._forward_logits(model, x)
                clean_pred = clean_logits.argmax(dim=-1)

            y_ref = clean_pred.detach()
            fgsm_x = self._fgsm(model, x, y_ref, epsilon)
            pgd_x = self._pgd(model, x, y_ref, epsilon, alpha, pgd_steps)

            with torch.no_grad():
                fgsm_pred = self._forward_logits(model, fgsm_x).argmax(dim=-1)
                pgd_pred = self._forward_logits(model, pgd_x).argmax(dim=-1)

            fgsm_success = float((fgsm_pred != clean_pred).float().mean().item())
            pgd_success = float((pgd_pred != clean_pred).float().mean().item())
            max_success = max(fgsm_success, pgd_success)

            severity = self._severity_from_success(max_success, config=cfg)
            finding = Finding(
                title=f"Adversarial vulnerability score: {max_success:.1%}",
                description=(
                    f"FGSM changed predictions in {fgsm_success:.1%} of probes; "
                    f"PGD changed predictions in {pgd_success:.1%} of probes."
                ),
                severity=severity,
                confidence=max_success,
                mitre_id="AI-A1002",
                evidence={
                    "num_samples": int(x.shape[0]),
                    "epsilon": epsilon,
                    "alpha": alpha,
                    "pgd_steps": pgd_steps,
                    "fgsm_success_rate": fgsm_success,
                    "pgd_success_rate": pgd_success,
                },
                recommendation=(
                    "Consider adversarial training, confidence calibration, and input preprocessing "
                    "for high-risk deployments."
                ),
            )

            return ScanResult(
                scanner_name=self.name,
                scanner_version=self.version,
                findings=[finding],
            )

        except Exception as e:
            log.exception("Adversarial scan failed")
            return ScanResult(
                scanner_name=self.name,
                scanner_version=self.version,
                findings=[
                    Finding(
                        title="Adversarial scan failed",
                        description=str(e),
                        severity=Severity.LOW,
                        confidence=0.0,
                    )
                ],
                error=str(e),
            )

    def _supports_gradients(self, adapter: ModelAdapter, model: Any) -> bool:
        provider = getattr(adapter, "provider", "unknown")
        if provider in {"openai", "anthropic", "aws"}:
            return False
        return hasattr(model, "parameters")

    def _get_device(self, model: Any):
        import torch

        try:
            p = next(model.parameters())
            return p.device
        except Exception:
            return torch.device("cpu")

    def _build_probe_batch(
        self, model: Any, cfg: Dict[str, Any], num_samples: int, device, adapter=None
    ):
        import torch

        # Check if model is a text/language model (has vocab_size or uses token IDs)
        is_text_model = (
            hasattr(model.config, "vocab_size")
            or hasattr(model, "vocab_size")
            or hasattr(model, "wte")  # GPT-2 style
        )

        if "probe_inputs" in cfg:
            probe = cfg["probe_inputs"]
            if isinstance(probe, list):
                # Check if it's token IDs (integers) or embeddings (floats)
                if probe and isinstance(probe[0], (int, list)):
                    x = torch.tensor(probe, dtype=torch.long, device=device)
                else:
                    x = torch.tensor(probe, dtype=torch.float32, device=device)
            else:
                x = torch.tensor(probe, dtype=torch.float32, device=device)
            if x.dim() == 1:
                x = x.unsqueeze(0)
            return x

        shape = cfg.get("input_shape")
        if shape:
            # input_shape may include batch dim; we normalize to [batch, ...]
            if len(shape) >= 1 and shape[0] == num_samples:
                full_shape = tuple(shape)
            else:
                full_shape = (num_samples, *shape)
            if is_text_model:
                # For text models, create random token IDs
                vocab_size = getattr(model.config, "vocab_size", 50257)
                return torch.randint(0, vocab_size, full_shape, device=device, dtype=torch.long)
            return torch.randn(full_shape, device=device)

        # best effort inference for simple MLPs
        in_features = None
        for mod in model.modules() if hasattr(model, "modules") else []:
            if hasattr(mod, "in_features"):
                in_features = int(mod.in_features)
                break
        if in_features is not None:
            return torch.randn((num_samples, in_features), device=device)

        # Default: if text model, use token IDs
        if is_text_model:
            vocab_size = getattr(model.config, "vocab_size", 50257)
            return torch.randint(0, vocab_size, (num_samples, 16), device=device, dtype=torch.long)

        return None

    def _forward_logits(self, model: Any, x):
        out = model(x)
        if isinstance(out, tuple):
            out = out[0]
        if hasattr(out, "logits") and out.logits is not None:
            return out.logits
        # For some transformers outputs, logits might be at a different path
        if hasattr(out, "last_hidden_state"):
            return out.last_hidden_state
        return out

    def _fgsm(self, model: Any, x, y_ref, epsilon: float):
        import torch.nn.functional as F

        x_adv = x.detach().clone().requires_grad_(True)
        logits = self._forward_logits(model, x_adv)
        loss = F.cross_entropy(logits, y_ref)
        model.zero_grad(set_to_none=True)
        loss.backward()
        perturb = epsilon * x_adv.grad.sign()
        return (x_adv + perturb).detach()

    def _pgd(self, model: Any, x, y_ref, epsilon: float, alpha: float, steps: int):
        import torch
        import torch.nn.functional as F

        x_orig = x.detach()
        x_adv = x_orig.clone().detach()

        for _ in range(steps):
            x_adv.requires_grad_(True)
            logits = self._forward_logits(model, x_adv)
            loss = F.cross_entropy(logits, y_ref)
            model.zero_grad(set_to_none=True)
            loss.backward()
            grad = x_adv.grad.sign()
            x_adv = x_adv.detach() + alpha * grad
            delta = torch.clamp(x_adv - x_orig, min=-epsilon, max=epsilon)
            x_adv = (x_orig + delta).detach()

        return x_adv

    def _severity_from_success(
        self, success_rate: float, config: Optional[Dict[str, Any]] = None
    ) -> Severity:
        thresholds = (config or {}).get("severity_thresholds", {})
        critical = thresholds.get("critical", 0.8)
        high = thresholds.get("high", 0.6)
        medium = thresholds.get("medium", 0.3)
        low = thresholds.get("low", 0.1)

        if success_rate >= critical:
            return Severity.CRITICAL
        if success_rate >= high:
            return Severity.HIGH
        if success_rate >= medium:
            return Severity.MEDIUM
        if success_rate >= low:
            return Severity.LOW
        return Severity.INFO

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        schema = super().get_config_schema()
        schema["properties"]["severity_thresholds"] = {
            "type": "object",
            "properties": {
                "critical": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 0.8,
                },
                "high": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.6},
                "medium": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 0.3,
                },
                "low": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.1},
            },
            "description": "Override severity thresholds for attack success rates",
        }
        return schema
