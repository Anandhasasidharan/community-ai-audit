# Adding a New Scanner — Step-by-Step

> **Time to complete:** ~30 minutes
> **Goal:** Add a new vulnerability scanner that plugs into the framework.

## 1. Understand the Interface

A scanner implements `ScannerPlugin` which requires:

| Method | Purpose |
|--------|---------|
| `scan(model, adapter, config)` | Run the scan, return `ScanResult` |

Your scanner receives:
- `model`: The loaded model (from the adapter)
- `adapter`: The `ModelAdapter` instance (for `predict()`, `get_input_spec()`, etc.)
- `config`: Dict with user-provided configuration

Your scanner returns:
- `ScanResult` — a list of `Finding` objects with severity, confidence, evidence

## 2. Create Your Scanner File

Create `community_ai_audit/plugins/scanners/my_scanner.py`:

```python
"""My custom vulnerability scanner."""

from typing import Any, Dict, List, Optional
import logging

from community_ai_audit.core.interfaces import ScannerPlugin, ScanResult, Finding, Severity

log = logging.getLogger(__name__)

class MyScanner(ScannerPlugin):
    name = "my-scanner"
    description = "Detects XYZ vulnerabilities in AI models"
    version = "0.1.0"
    supported_model_types = []  # Empty = all types

    def scan(self, model: Any, adapter: Any, config: Optional[Dict[str, Any]] = None) -> ScanResult:
        cfg = config or {}
        threshold = cfg.get("threshold", 0.5)

        findings = []
        
        # --- Your detection logic here ---
        # Example: check for suspicious activations
        result = adapter.predict(model, [0.1, 0.2, 0.3])
        if some_condition(result, threshold):
            findings.append(
                Finding(
                    title="Suspicious activation pattern detected",
                    description="Model shows unexpected behavior...",
                    severity=Severity.HIGH,
                    confidence=0.85,
                    evidence={"activation": str(result), "threshold": threshold},
                    recommendation="Retrain model with XYZ mitigation.",
                )
            )
        # ---------------------------------

        return ScanResult(
            scanner_name=self.name,
            scanner_version=self.version,
            findings=findings,
            metadata={"threshold": threshold, "samples_checked": 100},
        )


def some_condition(result, threshold):
    # Replace with real detection logic
    return False
```

## 3. Test Your Scanner

```python
from community_ai_audit.plugins.scanners.my_scanner import MyScanner

scanner = MyScanner()
# model and adapter from AuditEngine.load_model(...)
result = scanner.scan(model, adapter)
print(f"Findings: {len(result.findings)}")
```

## 4. Run via CLI

```bash
community-ai-audit scan model.pt --provider local --scanners my-scanner
```

## Key Patterns

- **Batch processing**: Use `adapter.predict()` with batches when possible
- **Configuration**: Accept `threshold`, `num_samples`, etc. via `config`
- **Evidence**: Always attach reproducible evidence (inputs, outputs, metadata)
- **Confidence**: Score 0.0–1.0 based on signal strength

## Full Working Example

See `examples/minimal_scanner.py` for a complete minimal scanner.
