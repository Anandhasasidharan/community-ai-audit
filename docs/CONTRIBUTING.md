# Contributing

## Quick rules
- Keep plugins import-safe
- Prefer small, typed interfaces
- Add smoke tests for new plugin types
- Avoid hard dependencies in module top-level imports unless required

## Recommended workflow
1. Fork the repo
2. Create a feature branch
3. Add tests
4. Run `python -m unittest discover -s tests -v`
5. Open a PR

## Security note
This tool is intended for defensive research and audit workflows only.