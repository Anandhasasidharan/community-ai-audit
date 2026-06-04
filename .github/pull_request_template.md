## Description

Briefly describe what this PR does.

## Related Issue

Closes #ISSUE_NUMBER

## Type of Change

- [ ] Bug fix (non-breaking)
- [ ] New feature (adapter, scanner, connector, interpreter)
- [ ] Documentation update
- [ ] CI / build improvement
- [ ] Refactoring (no functional changes)

## Checklist

- [ ] I've read the [CONTRIBUTING.md](../CONTRIBUTING.md) guide
- [ ] My code follows the project style (Black, Ruff)
- [ ] I've added/updated tests
- [ ] All existing tests pass: `pytest -q`
- [ ] I've added type hints for new public APIs
- [ ] I've updated documentation if needed
- [ ] My changes are backward-compatible

## Test Plan

```
# How did you test this?
pytest -q
ruff check .
black --check community_ai_audit/ tests/ examples/
```

## Screenshots (if applicable)

## Additional Notes
