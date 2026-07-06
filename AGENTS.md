# AGENTS.md — community-ai-audit

## Entrypoints
- **CLI**: `python -m community_ai_audit` → `community_ai_audit.cli.main:main`
- **API**: `uvicorn community_ai_audit.api.server:app` — FastAPI with lifespan that calls `init_db()`
- **Worker**: `python -m community_ai_audit.core.worker` — ARQ background worker (needs Redis)

## Development Commands (verify each before commit)
```bash
pip install -e ".[dev]"        # install dev extras
pytest -x -q                   # 592 tests, ~35s
ruff check .                   # lint — 0 errors expected
black --check community_ai_audit/ tests/ examples/   # line-length=100
```

## Testing Quirks
- **API tests**: Must set `os.environ["DATABASE_URL"] = "sqlite://"` before importing app. Use `TestClient(app)` as context manager to trigger lifespan. Override `current_user` via `app.dependency_overrides[current_user]`.
- **Scanner tests**: Use `MockAdapter(response_string)` (returns same string on every `generate()` call) or `MockAdapterByPrompt({key: value}, default=...)` (matches substrings in prompt). Both live in `tests/test_golden_behavior.py`.
- **unittest.TestCase style**: Most tests use `unittest.TestCase` classes (not pure pytest functions), but a few API tests use pytest fixtures.
- **Scoring tests**: `RiskScore` fields are `Optional[float] = None` (missing dims default to None, not 100). `coverage` list tracks which dims had data. Re-normalized weighted average.

## Architecture
- **7 dimension scoring**: security, reliability, compliance, agent_risk, alignment, red_team, interpretability. Each produces `Optional[float]`; `None` = excluded from weighted average. Default weights in `RiskScore` model.
- **9 adapters**: huggingface, openai, anthropic, aws_bedrock, local, ollama, replicate, vertexai, groq. All must return `str` from `predict()` (no raw SDK objects).
- **Module renamed**: `mechinterp` → `behavioral_probes` (both `plugins/` and `tests/`). Import path is `community_ai_audit.plugins.behavioral_probes`.
- **Config precedence**: `default.yaml` → `--config PATH` → env vars → CLI args. Env vars use `COMMUNITY_AI_AUDIT_` prefix.
- **Auth**: stdlib-only — HMAC-SHA256 JWT, PBKDF2-HMAC-SHA256 password hashing (no Passlib/PyJWT).
- **Rate limiting**: in-memory dict (60 req/min/IP), no Redis dependency for basic usage.

## Docker
```bash
docker compose up -d     # starts redis, api (:8080), worker
docker build -t community-ai-audit .
```

## Project Config
- `pyproject.toml` based (setuptools). No `requirements.txt`.
- Black: `line-length = 100`, `target-version = py39`.
- Alembic migrations in `alembic/`.
- OpenCode skills in `.opencode/skills/` (spotme, ponytail, green-commits).
