[![CI](https://img.shields.io/badge/ci-pending-lightgrey.svg)](#)
[![PyPI](https://img.shields.io/badge/pypi-unreleased-lightgrey.svg)](#)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

# Community AI Security Audit Tool

A community-driven tool for auditing AI models for security vulnerabilities using interpretability techniques. Built for cybersecurity researchers, ML engineers, and AI safety enthusiasts.

## Features

- **Vulnerability Scanning** — Detect backdoors, adversarial vulnerabilities, data poisoning, model stealing risks, and membership inference.
- **Interpretability Analysis** — Apply integrated gradients, LIME, activation clustering, and more to explain model behavior.
- **Risk Scoring & Reporting** — Generate actionable reports (Markdown, JSON, HTML, SARIF) with severity scores and mitigation suggestions.
- **Plug & Play** — Swap any model provider, SIEM, or scanner without touching the core.
- **Community Sharing** — Share audit results, signatures, and detection rules via a lightweight database or git-based sharing.

## Installation

```bash
git clone https://github.com/your-org/community-ai-audit.git
cd community-ai-audit
pip install -e .
```

## Quick Start

```bash
# Discover all components
community-ai-audit discover

# Scan a local PyTorch model
community-ai-audit scan my_model.pt --provider local --scanners adversarial --probe-file examples/data/toy_probe.json

# Full audit with interpretability
community-ai-audit audit my_model.pt --provider local --profile standard --scanners adversarial backdoor --interpreters integrated-gradients --probe-file examples/data/toy_probe.json --input '[0.1,...'

# Generate report in HTML
community-ai-audit audit my_model.pt --provider local --output html --save report.html
```

## Supported Providers

| Adapter | Type | Works Offline | Setup |
|---------|------|--------------|-------|
| `local` | PyTorch, TF, ONNX | ✅ Yes | Install torch/tensorflow |
| `huggingface` | transformers, diffusers | ✅ Yes | Install transformers |
| `openai` | GPT-4o, o1, etc. | ❌ No | Set OPENAI_API_KEY |
| `anthropic` | Claude-3, etc. | ❌ No | Set ANTHROPIC_API_KEY |
| `aws_bedrock` | All Bedrock models | ❌ No | Set AWS creds |
| `ollama` | Local LLMs | ✅ Yes | Install ollama |

## Supported SIEMs

| Connector | Platform | Auth |
|-----------|----------|------|
| `splunk` | Splunk HEC | Token |
| `elastic` | Elastic Security | API Key |
| `datadog` | Datadog Logs | API Key |
| `sentinel` | Microsoft Sentinel | Shared Key |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Model     │────→│  Scanner(s)  │────→│  Findings   │
│   Adapter   │     └──────────────┘     └─────────────┘
│             │
│             │────→│ Interpreter  │────→│Attributions │
│             │     └──────────────┘     └─────────────┘
└─────────────┘              │                   │
                              ↓                   ↓
                         ┌────────────┐
                         │  Reporter  │
                         │ (md/json/  │
                         │  html/sf)  │
                         └────────────┘

[CLI] → [AuditEngine] → [Plugins] → [SIEM Connector]
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full architecture.

## Documentation

| Guide | Purpose |
|-------|---------|
| [ADAPTER_GUIDE.md](docs/ADAPTER_GUIDE.md) | Add a new model provider (30 min) |
| [SCANNER_GUIDE.md](docs/SCANNER_GUIDE.md) | Add a new vulnerability scanner (30 min) |
| [CONNECTOR_GUIDE.md](docs/CONNECTOR_GUIDE.md) | Add a new SIEM connector (30 min) |
| [INTERPRETER_GUIDE.md](docs/INTERPRETER_GUIDE.md) | Add a new interpreter (30 min) |
| [PLUGIN_GUIDE.md](docs/PLUGIN_GUIDE.md) | Quick reference for all plugins |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and data flow |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md) | Setup, workflow, PR checklist |
| [PHASE1_BENCHMARK.md](docs/PHASE1_BENCHMARK.md) | Benchmark reproducibility |
| [PHASE2_CONNECTORS.md](docs/PHASE2_CONNECTORS.md) | SIEM integration guide |

## Project Status

🚧 **Pre-release (v0.1.0)** — Core infrastructure in progress.

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for setup instructions and guidelines.

## License

MIT License — see [LICENSE](LICENSE).
