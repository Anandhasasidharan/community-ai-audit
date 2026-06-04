# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
