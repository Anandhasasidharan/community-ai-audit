# Contributing to Community AI Audit

Thank you for your interest! This project aims to make AI security auditing accessible, extensible, and community-driven.

## Quick Start

```bash
# Clone and install
git clone https://github.com/Anandhasasidharan/community-ai-audit.git
cd community-ai-audit

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"
```

## Development Workflow

1. **Pick an issue** — comment on it to claim it
2. **Create a branch** — `git checkout -b feat/my-feature`
3. **Write code** — follow the style guide below
4. **Run checks** — `ruff check . && black --check community_ai_audit/ tests/ examples/`
5. **Run tests** — `pytest -q`
6. **Commit** — use conventional commits (see below)
7. **Push and PR** — open a pull request

## Style Guide

- **Python**: 3.9+
- **Formatter**: Black (line-length=100)
- **Linter**: Ruff (all default rules)
- **Type hints**: Required for all public APIs
- **Docstrings**: Google-style for public interfaces

Run formatting:
```bash
black community_ai_audit/ tests/ examples/
ruff check . --fix
```

## Pull Request Guidelines

- Keep PRs focused on single concern
- Add tests for new functionality
- Update docs if public API changes
- Ensure all CI checks pass (lint, typecheck, test)
- Reference the issue: `Closes #123`

## Conventional Commits

```
feat(adapter): add Groq adapter
fix(connector): handle timeout in Splunk connector
test(core): add audit engine edge cases
docs(README): add Quickstart section
ci(actions): add Python 3.13 to matrix
```

## Adding a New Component

See the step-by-step guides:
- [Adapter Guide](docs/ADAPTER_GUIDE.md) — ~30 min
- [Scanner Guide](docs/SCANNER_GUIDE.md) — ~30 min
- [Connector Guide](docs/CONNECTOR_GUIDE.md) — ~30 min
- [Interpreter Guide](docs/INTERPRETER_GUIDE.md) — ~30 min

## Code of Conduct

All contributors must follow our [Code of Conduct](CODE_OF_CONDUCT.md).
