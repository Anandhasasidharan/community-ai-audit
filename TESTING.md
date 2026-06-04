# Testing Guide

## Test Strategy

The test suite is organized by layer:

```
tests/
├── test_smoke.py           # Basic import and CLI smoke tests
├── test_cli.py             # CLI command parsing and routing
├── test_core.py            # Core interfaces and data structures
├── test_registry.py        # Plugin discovery and registration
├── test_audit_engine.py    # AuditEngine end-to-end flows
├── test_connectors_smoke.py # Connector initialization (no network)
├── test_retry.py           # Retry/backoff utility
```

## Running Tests

```bash
# Install dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=community_ai_audit --cov-report=term-missing

# Run specific test file
pytest tests/test_registry.py

# Run with verbose output
pytest -v

# Run with warnings
pytest -W all
```

## Coverage Goals

| Layer | Target | Current |
|-------|--------|---------|
| Core (interfaces, registry) | 90%+ | ✅ |
| Audit engine | 85%+ | ✅ |
| Adapters | 80%+ | ⚠️ (mock-based) |
| Connectors | 80%+ | ❌ (requires credentials) |
| Scanners | 75%+ | ⚠️ (requires model) |
| Interpreters | 75%+ | ⚠️ (requires model) |

## Writing Tests

### Unit Tests

Test pure logic with no external dependencies:

```python
def test_severity_comparison():
    assert Severity.CRITICAL > Severity.HIGH
```

### Mock Tests

For adapters and connectors that make HTTP calls:

```python
@patch("requests.post")
def test_splunk_connector(mock_post):
    mock_post.return_value.status_code = 200
    conn = SplunkConnector()
    conn.connect({"token": "test", "host": "localhost"})
    status = conn.send_events([{"title": "test", "severity": "low"}])
    assert status == "success"
```

### Integration Tests

End-to-end flows with mocked model:

```python
@patch("community_ai_audit.adapters.huggingface_adapter.HuggingFaceAdapter.load_model")
def test_audit_flow(mock_load):
    engine = AuditEngine()
    engine.load_model("test-model", provider="huggingface")
    results = engine.audit(scanners=["backdoor"])
    assert results.total_findings >= 0
```

## CI Pipeline

Tests run on every push and PR for Python 3.10–3.12:

```yaml
# From .github/workflows/ci.yml
- name: Run tests
  run: python -m pytest -q --cov=community_ai_audit --cov-report=xml
```

## Smoke Tests

Connector smoke tests verify initialization without making network calls.
They check:
- Config parsing works
- Required fields are validated
- Default values are applied correctly
