"""
Watermark detection scanner.
Analyzes model weights for signs of watermarking or backdoor signatures.
White-box only (requires torch model access).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from community_ai_audit.core.interfaces import (
    ScannerPlugin,
    Finding,
    ScanResult,
    Severity,
    ModelAdapter,
)

log = logging.getLogger(__name__)


class WatermarkScanner(ScannerPlugin):
    """Detects potential watermarks or anomalous weight patterns in model layers.

    Black-box models (API-only) will receive an INFO finding explaining
    that watermark detection requires local weight access.
    """

    name = "watermark"
    description = "Detection of model watermarking and anomalous weight patterns"
    version = "0.1.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def scan(
        self, model: Any, adapter: ModelAdapter, config: Optional[Dict[str, Any]] = None
    ) -> ScanResult:
        cfg = {**self.config, **(config or {})}

        if not hasattr(model, "parameters"):
            return ScanResult(
                scanner_name=self.name,
                scanner_version=self.version,
                findings=[
                    Finding(
                        title="Watermark detection requires white-box model access",
                        description="This adapter does not expose model weights. Watermark detection "
                        "requires local access to the model's parameter tensors.",
                        severity=Severity.INFO,
                        confidence=0.6,
                        recommendation="Run this scanner with local/white-box models (HuggingFace, LocalAdapter).",
                    )
                ],
            )

        try:
            import torch

            findings: List[Finding] = []
            suspicious_layers: List[Dict[str, Any]] = []
            total_params = 0
            watermarked_params = 0

            threshold = float(cfg.get("sparsity_threshold", 0.99))
            weight_var_threshold = float(cfg.get("weight_var_threshold", 0.01))

            for name, param in model.named_parameters():
                total_params += 1
                weight = param.data
                if weight.numel() < 10:
                    continue

                # Check 1: Extreme sparsity (too many zeros → possible watermark)
                zero_frac = (weight == 0).float().mean().item()
                if zero_frac >= threshold and weight.numel() > 100:
                    suspicious_layers.append(
                        {
                            "layer": name,
                            "type": "extreme_sparsity",
                            "zero_fraction": round(zero_frac, 4),
                            "shape": list(weight.shape),
                        }
                    )
                    watermarked_params += 1

                # Check 2: Unusually low variance weights (all values nearly identical)
                weight_var = weight.var().item()
                if weight_var < weight_var_threshold and weight.numel() > 100:
                    suspicious_layers.append(
                        {
                            "layer": name,
                            "type": "low_variance",
                            "variance": round(weight_var, 6),
                            "shape": list(weight.shape),
                        }
                    )
                    watermarked_params += 1

                # Check 3: Periodic weight patterns (structured watermark)
                if weight.dim() >= 2 and weight.shape[0] >= 4 and weight.shape[1] >= 4:
                    weight_flat = weight.flatten()
                    if weight_flat.numel() >= 100:
                        # Look for suspiciously regular patterns via autocorrelation
                        center = weight_flat[: weight_flat.numel() // 2]
                        shifted = weight_flat[
                            weight_flat.numel() // 2 : weight_flat.numel() // 2 + len(center)
                        ]
                        if len(center) == len(shifted):
                            correlation = torch.nn.functional.cosine_similarity(
                                center.unsqueeze(0), shifted.unsqueeze(0)
                            ).item()
                            if abs(correlation) > 0.99:
                                suspicious_layers.append(
                                    {
                                        "layer": name,
                                        "type": "periodic_pattern",
                                        "autocorrelation": round(correlation, 4),
                                        "shape": list(weight.shape),
                                    }
                                )
                                watermarked_params += 1

            if suspicious_layers:
                findings.append(
                    Finding(
                        title=f"Potential watermark detected in {len(suspicious_layers)} layer(s)",
                        description=f"{watermarked_params}/{total_params} parameter groups show anomalous patterns "
                        f"(sparsity ≥{threshold}, variance <{weight_var_threshold}, "
                        f"or high autocorrelation).",
                        severity=Severity.HIGH if len(suspicious_layers) > 2 else Severity.MEDIUM,
                        confidence=min(0.9, 0.3 + 0.1 * len(suspicious_layers)),
                        mitre_id="AI-A1005",
                        evidence={
                            "suspicious_layers": suspicious_layers,
                            "total_layers_checked": total_params,
                            "anomalous_layers": watermarked_params,
                        },
                        recommendation=(
                            "Review suspicious layers for watermarking. "
                            "If confirmed, retrain the model or use weight-averaging "
                            "to mitigate embedded signatures."
                        ),
                    )
                )
            else:
                findings.append(
                    Finding(
                        title="No watermark patterns detected",
                        description=f"Checked {total_params} parameter groups. No extreme sparsity, "
                        f"low variance, or periodic patterns found.",
                        severity=Severity.INFO,
                        confidence=0.8,
                        recommendation="Periodically re-scan as part of supply chain security.",
                    )
                )

            return ScanResult(
                scanner_name=self.name,
                scanner_version=self.version,
                findings=findings,
            )

        except Exception as e:
            log.exception("Watermark scan failed")
            return ScanResult(
                scanner_name=self.name,
                scanner_version=self.version,
                findings=[
                    Finding(
                        title="Watermark scan failed",
                        description=str(e),
                        severity=Severity.LOW,
                        confidence=0.0,
                    )
                ],
                error=str(e),
            )

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        schema = super().get_config_schema()
        schema["properties"]["sparsity_threshold"] = {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "default": 0.99,
            "description": "Zero-fraction above which a layer is flagged as suspicious",
        }
        schema["properties"]["weight_var_threshold"] = {
            "type": "number",
            "minimum": 0,
            "default": 0.01,
            "description": "Weight variance below which a layer is flagged",
        }
        return schema
