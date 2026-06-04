# Plugin Guide

> **Goal:** Add a new component (adapter, connector, scanner, interpreter, or reporter) to the framework.

## Quick Reference

| Component | Base Class | Method(s) | File Location |
|-----------|-----------|-----------|---------------|
| **Adapter** | `ModelAdapter` | `connect()`, `disconnect()`, `get_model()`, `predict()`, `get_input_spec()` | `adapters/my_adapter.py` |
| **SIEM Connector** | `SIEMConnector` | `connect()`, `send_batch()`, `query()` | `connectors/my_connector.py` |
| **Scanner** | `ScannerPlugin` | `scan()` | `plugins/scanners/my_scanner.py` |
| **Interpreter** | `InterpreterPlugin` | `interpret()` | `plugins/interpreters/my_interpreter.py` |
| **Reporter** | `ReporterPlugin` | `render()` | `plugins/reporters/my_reporter.py` |

## Adding a Model Adapter

Implement `ModelAdapter` or `TextModelAdapter`:

```python
from community_ai_audit.core.interfaces import TextModelAdapter, ModelType

class MyAdapter(TextModelAdapter):
    name = "myprovider"
    provider = "myprovider"
    supported_types = [ModelType.TEXT]

    def connect(self, config):
        self._api_key = config.get("api_key")

    def predict(self, model, inputs, **kwargs):
        # Call your API
        return {"outputs": [...]}

    # ... implement remaining methods
```

Register it:

```python
# In community_ai_audit/adapters/__init__.py
from .my_adapter import MyAdapter
```

Full guide: [ADAPTER_GUIDE.md](ADAPTER_GUIDE.md)

## Adding a SIEM Connector

Implement `SIEMConnector`:

```python
from community_ai_audit.core.interfaces import SIEMConnector

class MyConnector(SIEMConnector):
    name = "myplatform"

    def connect(self, config):
        self._url = config["url"]

    def send_batch(self, events, event_type="audit"):
        # POST to your platform
        return {"success": len(events), "failed": 0}

    def query(self, query, time_range=None):
        return []
```

Full guide: [CONNECTOR_GUIDE.md](CONNECTOR_GUIDE.md)

## Adding a Scanner

Implement `ScannerPlugin`:

```python
from community_ai_audit.core.interfaces import ScannerPlugin, ScanResult, Finding, Severity

class MyScanner(ScannerPlugin):
    name = "my-scanner"
    description = "Detects XYZ vulnerability"

    def scan(self, model, adapter, config=None):
        # Your detection logic
        finding = Finding(
            title="Suspicious pattern detected",
            description="...",
            severity=Severity.HIGH,
            confidence=0.85,
        )
        return ScanResult(
            scanner_name=self.name,
            scanner_version=self.version,
            findings=[finding],
        )
```

Full guide: [SCANNER_GUIDE.md](SCANNER_GUIDE.md)

## Adding an Interpreter

Implement `InterpreterPlugin`:

```python
from community_ai_audit.core.interfaces import InterpreterPlugin, InterpretationResult

class MyInterpreter(InterpreterPlugin):
    name = "my-interpreter"

    def interpret(self, model, adapter, inputs, target=None, config=None):
        # Compute attributions
        return InterpretationResult(
            interpreter_name=self.name,
            attributions={"feature_1": 0.8},
            summary="Feature 1 is most important",
        )
```

Full guide: [INTERPRETER_GUIDE.md](INTERPRETER_GUIDE.md)

## Adding a Reporter

Implement `ReporterPlugin`:

```python
from community_ai_audit.core.interfaces import ReporterPlugin

class CSVReporter(ReporterPlugin):
    name = "csv"
    supported_formats = ["csv"]

    def render(self, scan_results, interpret_results, metadata):
        # Convert findings to CSV
        lines = ["scanner,title,severity,confidence"]
        for result in scan_results:
            for f in result.findings:
                lines.append(f"{result.scanner_name},{f.title},{f.severity.value},{f.confidence}")
        return "\n".join(lines)
```

## Discovery

Plugins are auto-discovered via:

1. **Built-in scanning**: Modules in `community_ai_audit/plugins/`
2. **Entry points**: Packages declare `[project.entry-points."community_ai_audit.plugins"]`
3. **User paths**: Set `COMMUNITY_AI_AUDIT_PLUGIN_PATH=/path/to/plugins`

### Entry Point Example

In your package's `pyproject.toml`:

```toml
[project.entry-points."community_ai_audit.plugins"]
my_scanner = "my_package.scanners:MyScanner"
```

## Testing Your Plugin

```bash
# Run all tests
python -m unittest discover -s tests -v

# Test just your plugin
python -m unittest tests.test_core.TestAuditOrchestrator.test_scanner -v
```

## Example Plugins

See the `examples/` directory for minimal working examples:
- `examples/minimal_adapter.py` — Dummy HTTP adapter
- `examples/minimal_scanner.py` — Variance detector
- `examples/minimal_connector.py` — File-based SIEM
- `examples/minimal_interpreter.py` — Gradient-like attributions
