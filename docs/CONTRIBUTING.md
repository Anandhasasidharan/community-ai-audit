# Contributing

Thank you for your interest in contributing to the Community AI Security Audit Tool! This guide will get you up and running in minutes.

## Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/community-ai-audit.git
cd community-ai-audit

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install in editable mode with dev dependencies
pip install -e ".[dev]"

# 4. Verify tests pass
python -m unittest discover -s tests -v
```

## Adding a New Component

### Adapter (30 min)

1. Read [ADAPTER_GUIDE.md](ADAPTER_GUIDE.md)
2. Create `community_ai_audit/adapters/my_adapter.py`
3. Register in `community_ai_audit/adapters/__init__.py`
4. Add unit tests in `tests/`
5. Run tests

### Scanner (30 min)

1. Read [SCANNER_GUIDE.md](SCANNER_GUIDE.md)
2. Create `community_ai_audit/plugins/scanners/my_scanner.py`
3. Register in `community_ai_audit/plugins/scanners/__init__.py`
4. Add unit tests in `tests/`
5. Run tests

### Interpreter (30 min)

1. Read [INTERPRETER_GUIDE.md](INTERPRETER_GUIDE.md)
2. Create `community_ai_audit/plugins/interpreters/my_interpreter.py`
3. Register in `community_ai_audit/plugins/interpreters/__init__.py`
4. Add unit tests in `tests/`
5. Run tests

### SIEM Connector (30 min)

1. Read [CONNECTOR_GUIDE.md](CONNECTOR_GUIDE.md)
2. Create `community_ai_audit/connectors/my_connector.py`
3. Register in `community_ai_audit/connectors/__init__.py`
4. Add tests in `tests/test_connectors_smoke.py`
5. Run tests

## Code Style

- Use type hints
- Keep modules import-safe (no hard deps at top-level unless required)
- Add docstrings for public methods
- Follow PEP 8

## Testing

```bash
# Run all tests
python -m unittest discover -s tests -v

# Run specific test file
python -m unittest tests.test_core -v

# Run smoke tests only
python -m unittest tests.test_smoke -v
```

## Pull Request Checklist

- [ ] Tests pass locally
- [ ] New code has tests
- [ ] Docstrings updated
- [ ] README/docs updated if needed
- [ ] CHANGELOG.md updated

## Security

This tool is intended for defensive research and audit workflows only. Please do not use it for malicious purposes.
