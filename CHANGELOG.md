# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0](https://github.com/Anandhasasidharan/community-ai-audit/compare/v0.8.0...v0.9.0) (2026-07-06)


### Features

* **usage:** add usage metering middleware and GET /usage endpoint ([e153050](https://github.com/Anandhasasidharan/community-ai-audit/commit/e1530506ecb78d3566435d63081245f89568c239))


### Bug Fixes

* **adapters:** return str from predict() instead of raw SDK objects ([d23c9ab](https://github.com/Anandhasasidharan/community-ai-audit/commit/d23c9abeefa3c877980fd1f44dc6b8ea633f361d))
* **scoring:** return None for missing dimensions, add coverage tracking ([449a271](https://github.com/Anandhasasidharan/community-ai-audit/commit/449a271053962881d7c33857ebe5dad9255658fb))
* **sycophancy:** replace agreement/disagreement prompts with paired-topic flip detection ([7b2918e](https://github.com/Anandhasasidharan/community-ai-audit/commit/7b2918e39d0a996b1b8dcb6f940e4bd9e55de823))


### Documentation

* add Methodology and Limitations section to README ([292ffa5](https://github.com/Anandhasasidharan/community-ai-audit/commit/292ffa56e6d39c28c196696bcc06e5cf922f62b6))

## [0.8.0](https://github.com/Anandhasasidharan/community-ai-audit/compare/v0.7.0...v0.8.0) (2026-06-27)


### Features

* **api:** audit submission and scanner listing endpoints ([987d2d0](https://github.com/Anandhasasidharan/community-ai-audit/commit/987d2d0091f5c1a215911f78eab79d6ac2e1472b))
* **api:** FastAPI server scaffold with health check routes ([249c956](https://github.com/Anandhasasidharan/community-ai-audit/commit/249c95681d12b447838926c8f6f0c6dc013846c9))
* **api:** FastAPI server wiring all routes with rate limiting middleware ([f5962a3](https://github.com/Anandhasasidharan/community-ai-audit/commit/f5962a34afb4c4c2d23457cbcc93feff09645c88))
* **api:** user registration and login endpoints ([efa243f](https://github.com/Anandhasasidharan/community-ai-audit/commit/efa243fa60ac7afdf44a20a5a1dec5659d09a344))
* **auth:** JWT, password hashing, and API key management ([9e67c76](https://github.com/Anandhasasidharan/community-ai-audit/commit/9e67c7618b0d9c5f706bc0f86f96e342903752a1))
* CI/CD integration, model card output, ponytail cleanup, and three new subcommands ([9c858fe](https://github.com/Anandhasasidharan/community-ai-audit/commit/9c858fecc9f983f251dff51baf4bc31558cedfdb))
* **cli:** migrate all command handlers to Rich-based UI ([32e91c3](https://github.com/Anandhasasidharan/community-ai-audit/commit/32e91c3e77e019cf901047f1504ed9aa8cbcfe8e))
* **cli:** structured logging, graceful shutdown, health subcommand ([6f8e782](https://github.com/Anandhasasidharan/community-ai-audit/commit/6f8e7826c4df74cd6922cec478038ef981cd4816))
* **db:** SQLAlchemy models and Alembic migration scaffold ([01fae4b](https://github.com/Anandhasasidharan/community-ai-audit/commit/01fae4bdfd5d20e87a7573a8f5747efc713eacdd))
* **docker:** multi-service docker-compose with api, worker, redis ([af4d7ef](https://github.com/Anandhasasidharan/community-ai-audit/commit/af4d7effde825e18a979c34b2b8b718b863d4305))
* **projects:** project CRUD and scoped audit submissions ([a7613ba](https://github.com/Anandhasasidharan/community-ai-audit/commit/a7613baefc1f5874463e6a48107f23e42b6109ea))
* **scheduler:** cron-based recurring audit scheduling ([36efe02](https://github.com/Anandhasasidharan/community-ai-audit/commit/36efe027137e4031a4b1679e8c6569bcaddcc1d7))
* **sdk:** Python client library for the audit API ([ffa3314](https://github.com/Anandhasasidharan/community-ai-audit/commit/ffa33141e49c2e9fc923c6c22322fc0700bfdee0))
* v0.7.0 - Red Team, Mech Interp, Alignment, Scoring Engine, Dashboard, Trend Tracking ([061aa8e](https://github.com/Anandhasasidharan/community-ai-audit/commit/061aa8e41d1888356677d0d068b0d7609ca1866a))
* **webhooks:** deliver audit results to external URLs ([4241348](https://github.com/Anandhasasidharan/community-ai-audit/commit/42413482542e48041a0badd3697f1bf1712f2f0e))
* **worker:** ARQ worker with periodic schedule check and webhook delivery ([ccf3783](https://github.com/Anandhasasidharan/community-ai-audit/commit/ccf37837991193ebe3bc9687bfd891411d508a4f))


### Bug Fixes

* align version to 0.6.0 (match remote release) ([70e6402](https://github.com/Anandhasasidharan/community-ai-audit/commit/70e64026e16f42c27da332deb0742a7386fd11ec))


### Documentation

* add exit code contract ([af0354d](https://github.com/Anandhasasidharan/community-ai-audit/commit/af0354d4fe52138f19e759dfa483f26266397e4f))
* rewrite README with Pretext-structured layout, API docs, mermaid diagram, and enhanced sections ([601e9d7](https://github.com/Anandhasasidharan/community-ai-audit/commit/601e9d78b65baa3d67c5363da5078e4af49f1d75))

## [0.7.0](https://github.com/Anandhasasidharan/community-ai-audit/compare/v0.6.1...v0.7.0) (2026-06-27)


### Features

* **api:** audit submission and scanner listing endpoints ([987d2d0](https://github.com/Anandhasasidharan/community-ai-audit/commit/987d2d0091f5c1a215911f78eab79d6ac2e1472b))
* **api:** FastAPI server scaffold with health check routes ([249c956](https://github.com/Anandhasasidharan/community-ai-audit/commit/249c95681d12b447838926c8f6f0c6dc013846c9))
* **api:** FastAPI server wiring all routes with rate limiting middleware ([f5962a3](https://github.com/Anandhasasidharan/community-ai-audit/commit/f5962a34afb4c4c2d23457cbcc93feff09645c88))
* **api:** user registration and login endpoints ([efa243f](https://github.com/Anandhasasidharan/community-ai-audit/commit/efa243fa60ac7afdf44a20a5a1dec5659d09a344))
* **auth:** JWT, password hashing, and API key management ([9e67c76](https://github.com/Anandhasasidharan/community-ai-audit/commit/9e67c7618b0d9c5f706bc0f86f96e342903752a1))
* CI/CD integration, model card output, ponytail cleanup, and three new subcommands ([9c858fe](https://github.com/Anandhasasidharan/community-ai-audit/commit/9c858fecc9f983f251dff51baf4bc31558cedfdb))
* **cli:** structured logging, graceful shutdown, health subcommand ([6f8e782](https://github.com/Anandhasasidharan/community-ai-audit/commit/6f8e7826c4df74cd6922cec478038ef981cd4816))
* **db:** SQLAlchemy models and Alembic migration scaffold ([01fae4b](https://github.com/Anandhasasidharan/community-ai-audit/commit/01fae4bdfd5d20e87a7573a8f5747efc713eacdd))
* **docker:** multi-service docker-compose with api, worker, redis ([af4d7ef](https://github.com/Anandhasasidharan/community-ai-audit/commit/af4d7effde825e18a979c34b2b8b718b863d4305))
* **projects:** project CRUD and scoped audit submissions ([a7613ba](https://github.com/Anandhasasidharan/community-ai-audit/commit/a7613baefc1f5874463e6a48107f23e42b6109ea))
* **scheduler:** cron-based recurring audit scheduling ([36efe02](https://github.com/Anandhasasidharan/community-ai-audit/commit/36efe027137e4031a4b1679e8c6569bcaddcc1d7))
* **sdk:** Python client library for the audit API ([ffa3314](https://github.com/Anandhasasidharan/community-ai-audit/commit/ffa33141e49c2e9fc923c6c22322fc0700bfdee0))
* **webhooks:** deliver audit results to external URLs ([4241348](https://github.com/Anandhasasidharan/community-ai-audit/commit/42413482542e48041a0badd3697f1bf1712f2f0e))
* **worker:** ARQ worker with periodic schedule check and webhook delivery ([ccf3783](https://github.com/Anandhasasidharan/community-ai-audit/commit/ccf37837991193ebe3bc9687bfd891411d508a4f))


### Documentation

* add exit code contract ([af0354d](https://github.com/Anandhasasidharan/community-ai-audit/commit/af0354d4fe52138f19e759dfa483f26266397e4f))

## [0.6.1](https://github.com/Anandhasasidharan/community-ai-audit/compare/v0.6.0...v0.6.1) (2026-06-25)


### Bug Fixes

* align version to 0.6.0 (match remote release) ([70e6402](https://github.com/Anandhasasidharan/community-ai-audit/commit/70e64026e16f42c27da332deb0742a7386fd11ec))

## [0.6.0](https://github.com/Anandhasasidharan/community-ai-audit/compare/v0.5.0...v0.6.0) (2026-06-25)


### Features

* **cli:** migrate all command handlers to Rich-based UI ([32e91c3](https://github.com/Anandhasasidharan/community-ai-audit/commit/32e91c3e77e019cf901047f1504ed9aa8cbcfe8e))
* v0.7.0 - Red Team, Mech Interp, Alignment, Scoring Engine, Dashboard, Trend Tracking ([061aa8e](https://github.com/Anandhasasidharan/community-ai-audit/commit/061aa8e41d1888356677d0d068b0d7609ca1866a))

## [0.5.0](https://github.com/Anandhasasidharan/community-ai-audit/compare/v0.4.0...v0.5.0) (2026-06-25)


### Features

* **cli:** migrate all command handlers to Rich-based UI ([32e91c3](https://github.com/Anandhasasidharan/community-ai-audit/commit/32e91c3e77e019cf901047f1504ed9aa8cbcfe8e))

## [0.4.0](https://github.com/Anandhasasidharan/community-ai-audit/compare/v0.3.0...v0.4.0) (2026-06-10)


### Features

* v0.7.0 - Red Team, Mech Interp, Alignment, Scoring Engine, Dashboard, Trend Tracking ([061aa8e](https://github.com/Anandhasasidharan/community-ai-audit/commit/061aa8e41d1888356677d0d068b0d7609ca1866a))

## [0.3.0](https://github.com/Anandhasasidharan/community-ai-audit/compare/v0.2.0...v0.3.0) (2026-06-07)


### Features

* v0.5.0 - production readiness with advanced scanners, SIEM connectors, scheduling, RBAC, Helm chart, Docker, and air-gapped install ([94836b9](https://github.com/Anandhasasidharan/community-ai-audit/commit/94836b9a6812e8b53ff013e9f5f6f19ff2520a53))


### Bug Fixes

* huggingface_adapter _resolve_device handles missing torch ([f389ff7](https://github.com/Anandhasasidharan/community-ai-audit/commit/f389ff72fae0ddfabe1e82b3e382613ee73faf36))
* make local_adapter, scheduler tests, watermark tests optional-dep-safe ([3f6f6d1](https://github.com/Anandhasasidharan/community-ai-audit/commit/3f6f6d101a3446f95d6c13869cf41aabff2158b3))
* make torch-dependent test collection work without torch ([eb4773b](https://github.com/Anandhasasidharan/community-ai-audit/commit/eb4773bb7909379867d5d14eff7226756a914c4d))
* move torch from core deps to optional to reduce install size ([a650ee1](https://github.com/Anandhasasidharan/community-ai-audit/commit/a650ee146570f14679db4750c2918fc2d29aa452))
* production hardening across all tiers ([b2d76d3](https://github.com/Anandhasasidharan/community-ai-audit/commit/b2d76d3be983638f25b28ac8a46b8b6dbc3572dd))


### Documentation

* add community files, templates, and CI improvements ([410308b](https://github.com/Anandhasasidharan/community-ai-audit/commit/410308b8012f13d69011945579487462a5024aa6))
* rewrite README for professional audience ([3369dad](https://github.com/Anandhasasidharan/community-ai-audit/commit/3369dad13d185959d1b5f9c780d84a44ff6a95e4))

## [0.2.0](https://github.com/Anandhasasidharan/community-ai-audit/compare/v0.1.2...v0.2.0) (2026-06-07)


### Features

* v0.5.0 - production readiness with advanced scanners, SIEM connectors, scheduling, RBAC, Helm chart, Docker, and air-gapped install ([94836b9](https://github.com/Anandhasasidharan/community-ai-audit/commit/94836b9a6812e8b53ff013e9f5f6f19ff2520a53))


### Bug Fixes

* huggingface_adapter _resolve_device handles missing torch ([f389ff7](https://github.com/Anandhasasidharan/community-ai-audit/commit/f389ff72fae0ddfabe1e82b3e382613ee73faf36))
* make local_adapter, scheduler tests, watermark tests optional-dep-safe ([3f6f6d1](https://github.com/Anandhasasidharan/community-ai-audit/commit/3f6f6d101a3446f95d6c13869cf41aabff2158b3))
* make torch-dependent test collection work without torch ([eb4773b](https://github.com/Anandhasasidharan/community-ai-audit/commit/eb4773bb7909379867d5d14eff7226756a914c4d))

## [0.1.2](https://github.com/Anandhasasidharan/community-ai-audit/compare/v0.1.1...v0.1.2) (2026-06-04)


### Documentation

* rewrite README for professional audience ([3369dad](https://github.com/Anandhasasidharan/community-ai-audit/commit/3369dad13d185959d1b5f9c780d84a44ff6a95e4))

## [0.1.1](https://github.com/Anandhasasidharan/community-ai-audit/compare/v0.1.0...v0.1.1) (2026-06-04)


### Bug Fixes

* move torch from core deps to optional to reduce install size ([a650ee1](https://github.com/Anandhasasidharan/community-ai-audit/commit/a650ee146570f14679db4750c2918fc2d29aa452))

## 0.1.0 (2026-06-04)


### Documentation

* add community files, templates, and CI improvements ([410308b](https://github.com/Anandhasasidharan/community-ai-audit/commit/410308b8012f13d69011945579487462a5024aa6))

## [Unreleased]

## [0.1.0] - 2026-06-04

### Added
- **Vulnerability Scanning** — Backdoor detection via activation clustering, adversarial vulnerability detection via FGSM/PGD.
- **Interpretability Analysis** — Integrated Gradients and LIME for explainability.
- **Risk Scoring** — Per-scanner and session-level risk scores across severity/confidence.
- **Reports** — Markdown, JSON, and HTML report generation via `ReportGenerator`.
- **Model Adapters** — Plug-and-play adapters for HuggingFace, OpenAI, Anthropic, AWS Bedrock, Ollama, and local PyTorch/TensorFlow/ONNX.
- **SIEM Connectors** — Splunk (HEC), Elastic Security, Datadog Logs, and Microsoft Sentinel with retry/backoff.
- **Shared Utilities** — Exponential-backoff retry with jitter, event schema validation, dead-letter logging, and severity normalization.
- **CLI** — `discover`, `scan`, `interpret`, and `audit` commands with profile support.
- **CI/CD** — GitHub Actions workflow with lint (ruff), format check (black), type check (mypy), unit tests across Python 3.10–3.12, build verification, and TestPyPI/PyPI publish on version tags.
- **Documentation** — README with provider/connector matrices, architecture docs, contributing guide, and step-by-step guides for creating adapters, connectors, scanners, and interpreters.
- **Working Examples** — Minimal self-contained examples (`minimal_adapter.py`, `minimal_scanner.py`, `minimal_connector.py`, `minimal_interpreter.py`).
- **Provider Configs** — YAML examples for HuggingFace, OpenAI, Anthropic, local, and Ollama.
- **Tests** — 26+ unit tests covering CLI, connectors, registry, audit engine, and retry logic.

### Notes
- This is the first public pre-release. Core infrastructure is stable; additional scanners and connectors are planned.

### Contributors
- Community AI Security Audit Tool contributors
