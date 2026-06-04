"""Minimal working scanner example.

Demonstrates a custom vulnerability scanner that detects
anomalous activation patterns.

Run:
    python examples/minimal_scanner.py
"""

from typing import Any, Dict, Optional
import random

from community_ai_audit.core.interfaces import ScannerPlugin, ScanResult, Finding, Severity


class MinimalScanner(ScannerPlugin):
    """Dummy scanner that flags models with high output variance."""

    name = "minimal-demo"
    description = "Flags models with high output variance (demo scanner)"
    version = "0.1.0"
    supported_model_types = []  # All types

    def scan(self, model: Any, adapter: Any, config: Optional[Dict[str, Any]] = None) -> ScanResult:
        cfg = config or {}
        threshold = cfg.get("variance_threshold", 0.3)
        num_samples = cfg.get("num_samples", 50)

        print(f"[scan] Running {self.name} with threshold={threshold}, num_samples={num_samples}")

        # Simulate: run multiple predictions and measure variance
        predictions = []
        for _ in range(num_samples):
            sample_input = [random.random() for _ in range(10)]
            pred = adapter.predict(model, sample_input)
            # Use first output as scalar measure
            outputs = pred.get("outputs", [0.5])
            predictions.append(outputs[0])

        variance = sum((p - (sum(predictions) / len(predictions))) ** 2 for p in predictions) / len(predictions)
        print(f"[scan] Measured variance: {variance:.4f} (threshold: {threshold})")

        findings = []
        if variance > threshold:
            findings.append(
                Finding(
                    title="High output variance detected",
                    description=f"Model predictions show high variance ({variance:.3f} > threshold {threshold}). "
                                f"This may indicate instability or adversarial sensitivity.",
                    severity=Severity.HIGH,
                    confidence=min(variance, 0.95),
                    evidence={"variance": variance, "threshold": threshold, "num_samples": num_samples},
                    recommendation="Retrain with data augmentation or add adversarial training.",
                )
            )
        else:
            findings.append(
                Finding(
                    title="Output variance within acceptable range",
                    description=f"Model variance {variance:.3f} is below threshold {threshold}.",
                    severity=Severity.INFO,
                    confidence=0.9,
                    evidence={"variance": variance, "threshold": threshold},
                )
            )

        return ScanResult(
            scanner_name=self.name,
            scanner_version=self.version,
            findings=findings,
            metadata={"variance": variance, "num_samples": num_samples},
        )


if __name__ == "__main__":
    # Simple self-test without full engine
    from examples.minimal_adapter import DummyHTTPAdapter

    adapter = DummyHTTPAdapter()
    adapter.connect({"api_key": "test"})
    model = adapter.get_model("test-model")

    scanner = MinimalScanner()
    result = scanner.scan(model, adapter)

    print(f"\nScanner: {result.scanner_name}")
    print(f"Findings: {len(result.findings)}")
    for f in result.findings:
        print(f"  - {f.severity.value}: {f.title} (confidence: {f.confidence:.2f})")
