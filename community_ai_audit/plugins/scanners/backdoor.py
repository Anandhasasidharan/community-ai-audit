"""
Backdoor vulnerability scanner.
Phase-1 implementation: activation anomaly detection via clustering.

This scanner is designed to be practical for local/white-box torch models.
It runs a probe batch through the model, captures intermediate activations,
then flags small anomalous clusters that may indicate Trojan triggers.
"""

from typing import Any, Dict, List, Optional
import logging

from community_ai_audit.core.interfaces import (
    ScannerPlugin,
    Finding,
    ScanResult,
    Severity,
    ModelAdapter,
)

log = logging.getLogger(__name__)


class BackdoorScanner(ScannerPlugin):
    name = "backdoor"
    description = "Detection of backdoor/Trojan attacks via activation clustering"
    version = "0.2.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def scan(
        self,
        model: Any,
        adapter: ModelAdapter,
        config: Optional[Dict[str, Any]] = None,
    ) -> ScanResult:
        cfg = {**self.config, **(config or {})}
        n_clusters = int(cfg.get("num_clusters", 5))
        threshold = float(cfg.get("activation_threshold", 0.85))
        sample_size = int(cfg.get("sample_size", 512))

        if not hasattr(model, "modules"):
            return ScanResult(
                scanner_name=self.name,
                scanner_version=self.version,
                findings=[
                    Finding(
                        title="Backdoor scan limited: model is not white-box",
                        description=(
                            "Activation clustering requires direct module access. "
                            "Use a local/white-box model for this scanner."
                        ),
                        severity=Severity.INFO,
                        confidence=0.6,
                        recommendation="Run this scanner with provider=local or another white-box adapter.",
                    )
                ],
            )

        try:
            activations = self._extract_activations(model, cfg, adapter)
        except Exception as e:
            log.exception("Activation extraction failed")
            return ScanResult(
                scanner_name=self.name,
                scanner_version=self.version,
                findings=[
                    Finding(
                        title="Backdoor scan failed",
                        description=str(e),
                        severity=Severity.LOW,
                        confidence=0.0,
                    )
                ],
                error=str(e),
            )

        if not activations:
            return ScanResult(
                scanner_name=self.name,
                scanner_version=self.version,
                findings=[
                    Finding(
                        title="No activations captured",
                        description=(
                            "Scanner could not capture usable layer activations. "
                            "Set `input_shape` in scanner config, e.g. [16]."
                        ),
                        severity=Severity.LOW,
                        confidence=0.4,
                    )
                ],
            )

        findings: List[Finding] = []

        for layer_name, tensor in activations.items():
            flat = self._flatten_data(tensor)
            if not flat:
                continue

            outliers = self._run_clustering(
                flat,
                n_clusters=n_clusters,
                threshold=threshold,
                sample_size=sample_size,
            )

            if outliers:
                confidence = min(max(outliers), 0.99)
                thresholds = cfg.get("severity_thresholds", {})
                high_thresh = thresholds.get("high", 0.75)
                severity = Severity.HIGH if confidence >= high_thresh else Severity.MEDIUM
                findings.append(
                    Finding(
                        title=f"Activation anomaly detected in {layer_name}",
                        description=(
                            f"Layer '{layer_name}' produced suspiciously small activation cluster(s) "
                            f"during probe inference."
                        ),
                        severity=severity,
                        confidence=confidence,
                        mitre_id="AI-A1003",
                        evidence={
                            "layer": layer_name,
                            "outlier_scores": outliers,
                            "num_vectors": len(flat),
                            "num_clusters": n_clusters,
                            "threshold": threshold,
                        },
                        recommendation=(
                            "Inspect this layer with targeted trigger search and compare against a clean baseline model."
                        ),
                    )
                )

        if not findings:
            findings.append(
                Finding(
                    title="No strong backdoor indicators detected",
                    description=(
                        "Activation clustering did not reveal statistically small suspicious clusters "
                        "on the generated probe batch."
                    ),
                    severity=Severity.INFO,
                    confidence=0.5,
                    evidence={"captured_layers": list(activations.keys())[:10]},
                    recommendation="Increase probe coverage or provide representative inputs for deeper analysis.",
                )
            )

        return ScanResult(
            scanner_name=self.name,
            scanner_version=self.version,
            findings=findings,
            metadata={"layers_analyzed": len(activations)},
        )

    def _extract_activations(self, model: Any, cfg: Dict[str, Any], adapter=None) -> Dict[str, Any]:
        import torch

        device = self._get_device(model)
        probe = self._build_probe_batch(model, cfg, device=device, adapter=adapter)
        if probe is None:
            return {}

        max_layers = int(cfg.get("max_layers", 16))
        target_layers = set(cfg.get("target_layers", []) or [])

        activations: Dict[str, Any] = {}
        handles = []

        # Capture leaf-module outputs only
        for name, module in model.named_modules():
            if len(list(module.children())) > 0:
                continue
            if target_layers and name not in target_layers:
                continue
            if len(handles) >= max_layers:
                break

            def _hook_factory(layer_name):
                def _hook(_mod, _inp, out):
                    if isinstance(out, torch.Tensor):
                        activations[layer_name] = out.detach().cpu()
                    elif (
                        isinstance(out, (tuple, list)) and out and isinstance(out[0], torch.Tensor)
                    ):
                        activations[layer_name] = out[0].detach().cpu()

                return _hook

            handles.append(module.register_forward_hook(_hook_factory(name)))

        try:
            model.eval()
            with torch.no_grad():
                _ = model(probe)
        finally:
            for h in handles:
                h.remove()

        return activations

    def _build_probe_batch(self, model: Any, cfg: Dict[str, Any], device, adapter=None):
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

        num_samples = int(cfg.get("sample_size", 128))
        input_shape = cfg.get("input_shape")
        if input_shape:
            if len(input_shape) >= 1 and input_shape[0] == num_samples:
                full = tuple(input_shape)
            else:
                full = (num_samples, *input_shape)
            if is_text_model:
                # For text models, create random token IDs
                vocab_size = getattr(model.config, "vocab_size", 50257)
                return torch.randint(0, vocab_size, full, device=device, dtype=torch.long)
            return torch.randn(full, device=device)

        in_features = None
        for m in model.modules() if hasattr(model, "modules") else []:
            if hasattr(m, "in_features"):
                in_features = int(m.in_features)
                break

        if in_features is not None:
            return torch.randn((num_samples, in_features), device=device)

        # Default: if text model, use token IDs
        if is_text_model:
            vocab_size = getattr(model.config, "vocab_size", 50257)
            return torch.randint(0, vocab_size, (num_samples, 16), device=device, dtype=torch.long)

        return None

    def _get_device(self, model: Any):
        import torch

        try:
            return next(model.parameters()).device
        except Exception:
            return torch.device("cpu")

    def _flatten_data(self, data: Any) -> List[List[float]]:
        import numpy as np

        arr = None
        if hasattr(data, "detach"):
            arr = data.detach().cpu().numpy()
        elif isinstance(data, (list, tuple)) and data:
            first = data[0]
            if hasattr(first, "detach"):
                arr = first.detach().cpu().numpy()
            else:
                arr = np.asarray(first)
        else:
            try:
                arr = np.asarray(data)
            except Exception:
                return []

        if arr is None or arr.size == 0:
            return []

        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        elif arr.ndim > 2:
            arr = arr.reshape(-1, arr.shape[-1])

        return arr.tolist()

    def _run_clustering(
        self,
        vectors: List[List[float]],
        n_clusters: int,
        threshold: float,
        sample_size: int,
    ) -> List[float]:
        import numpy as np
        import random
        from collections import Counter

        if len(vectors) < max(8, n_clusters * 2):
            return []

        sample = random.sample(vectors, min(sample_size, len(vectors)))
        X = np.asarray(sample, dtype=float)

        try:
            from sklearn.cluster import KMeans

            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
            labels = kmeans.fit_predict(X)
            counts = Counter(labels)
            total = len(labels)
            min_cluster_ratio = max(0.01, (1.0 - threshold) / float(max(1, n_clusters)))

            scores: List[float] = []
            for _, count in counts.items():
                ratio = count / float(total)
                if ratio < min_cluster_ratio:
                    scores.append(float(1.0 - ratio / min_cluster_ratio))
            return scores

        except Exception:
            # Fallback: simple distance-outlier score (if sklearn unavailable)
            mu = X.mean(axis=0)
            d = np.linalg.norm(X - mu, axis=1)
            q95 = float(np.quantile(d, 0.95))
            if q95 <= 0:
                return []
            tail = d[d > q95]
            if tail.size == 0:
                return []
            return [float(min(0.99, (tail.mean() - q95) / (q95 + 1e-9)))]

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        schema = super().get_config_schema()
        schema["properties"]["severity_thresholds"] = {
            "type": "object",
            "properties": {
                "high": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.75},
            },
            "description": "Override severity thresholds for anomaly confidence",
        }
        schema["properties"]["num_clusters"] = {
            "type": "integer",
            "minimum": 2,
            "default": 5,
            "description": "Number of KMeans clusters for activation analysis",
        }
        schema["properties"]["activation_threshold"] = {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "default": 0.85,
            "description": "Threshold for flagging anomalous activation clusters",
        }
        schema["properties"]["sample_size"] = {
            "type": "integer",
            "minimum": 64,
            "default": 512,
            "description": "Number of probe samples for activation extraction",
        }
        return schema
