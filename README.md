# Community AI Security Audit Tool

[![PyPI version](https://img.shields.io/pypi/v/community-ai-audit.svg)](https://pypi.org/project/community-ai-audit/)
[![Python versions](https://img.shields.io/pypi/pyversions/community-ai-audit.svg)](https://pypi.org/project/community-ai-audit/)
[![License](https://img.shields.io/github/license/anomalyco/community-ai-audit.svg)](LICENSE)

A plug-and-play, community-driven AI security audit framework. Scan any model (local, HF Hub, OpenAI, Anthropic, AWS Bedrock, Ollama) for vulnerabilities, interpret decisions, and push findings to your SIEM (Splunk, Elastic, Datadog, Sentinel).

## Features

- **Model Adapters**: HuggingFace, OpenAI, Anthropic, AWS Bedrock, Local (PyTorch/ONNX/SafeTensors), Ollama
- **Vulnerability Scanners**: Backdoor/Trojan detection (activation clustering), Adversarial robustness (FGSM/PGD)
- **Interpretability**: Integrated Gradients, LIME
- **SIEM Connectors**: Splunk HEC, Elastic/Elasticsearch, Datadog Logs, Microsoft Sentinel
- **Reporting**: Markdown, JSON, HTML
- **CLI**: `discover`, `scan`, `interpret`, `audit` commands
- **Extensible**: Plugin system for custom adapters, scanners, interpreters, connectors

## Quickstart

```bash
# Install
pip install community-ai-audit[hf]  # with HuggingFace support

# Discover available plugins
community-ai-audit discover

# Scan a HuggingFace model
community-ai-audit scan distilgpt2 --provider huggingface --profile quick

# Full audit (scan + interpret) with SIEM push
community-ai-audit audit meta-llama/Llama-3-8B-Instruct \
  --provider huggingface \
  --profile standard \
  --scanners backdoor adversarial \
  --interpreters integrated-gradients lime \
  --connectors splunk elastic \
  --config config/my_connectors.yaml
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      AuditEngine                                │
│  (orchestrates: load → scan → interpret → report → push)       │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   Adapters      │ │   Scanners      │ │  Interpreters   │
│  (load_model)   │ │  (scan model)   │ │ (explain model) │
├─────────────────┤ ├─────────────────┤ ├─────────────────┤
│ • HuggingFace   │ │ • Backdoor      │ │ • Integrated    │
│ • OpenAI        │ │ • Adversarial   │ │   Gradients     │
│ • Anthropic     │ │ • (custom)      │ │ • LIME          │
│ • AWS Bedrock   │ │                 │ │ • (custom)      │
│ • Local         │ │                 │ │                 │
│ • Ollama        │ │                 │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
                   ┌─────────────────────┐
                   │   Reporters         │
                   │ (markdown, json,    │
                   │  html)              │
                   └─────────────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │  SIEM Connectors    │
                   │ (push findings)     │
                   ├─────────────────────┤
                   │ • Splunk HEC        │
                   │ • Elastic           │
                   │ • Datadog           │
                   │ • Sentinel          │
                   │ • (custom)          │
                   └─────────────────────┘
```

## Provider Matrix

| Provider | Text | Image | Multimodal | Embedding | Auth |
|----------|------|-------|------------|-----------|------|
| HuggingFace | ✅ | ✅ | ✅ | ✅ | HF_TOKEN |
| OpenAI | ✅ | ✅ | ✅ | ✅ | OPENAI_API_KEY |
| Anthropic | ✅ | ❌ | ❌ | ❌ | ANTHROPIC_API_KEY |
| AWS Bedrock | ✅ | ✅ | ✅ | ✅ | AWS creds |
| Local (PyTorch) | ✅ | ✅ | ✅ | ✅ | None |
| Ollama | ✅ | ❌ | ❌ | ❌ | Local server |

## Installation

```bash
# Core only
pip install community-ai-audit

# With HuggingFace transformers
pip install community-ai-audit[hf]

# With TensorFlow support
pip install community-ai-audit[tf]

# All optional dependencies
pip install community-ai-audit[all]

# Development install
git clone https://github.com/anomalyco/community-ai-audit
cd community-ai-audit
pip install -e .[dev]
```

## Configuration

Create `config/my_config.yaml`:

```yaml
model:
  device: auto
  dtype: auto

scanners:
  backdoor:
    enabled: true
    num_clusters: 5
    activation_threshold: 0.85
  adversarial:
    enabled: true
    epsilon: 0.1
    pgd_steps: 10

connectors:
  splunk:
    hec_url: https://splunk.example.com:8088
    hec_token: ${SPLUNK_HEC_TOKEN}
    index: security
  elastic:
    url: https://es.example.com:9243
    api_key: ${ELASTICSEARCH_API_KEY}
```

Use with `--config config/my_config.yaml`.

## CLI Commands

### Discover
```bash
community-ai-audit discover
community-ai-audit discover --format json
```

### Scan
```bash
# Quick scan with defaults
community-ai-audit scan distilgpt2 --provider huggingface

# Custom profile and scanners
community-ai-audit scan model.pt --provider local \
  --profile deep \
  --scanners backdoor adversarial \
  --input-shape '[32, 768]' \
  --output markdown --save report.md
```

### Interpret
```bash
community-ai-audit interpret distilgpt2 --provider huggingface \
  --interpreters integrated-gradients lime \
  --input "The model should classify this as positive."
```

### Audit (Full Pipeline)
```bash
community-ai-audit audit meta-llama/Llama-3-8B-Instruct \
  --provider huggingface \
  --profile standard \
  --scanners backdoor adversarial \
  --interpreters integrated-gradients \
  --connectors splunk elastic \
  --config config/my_connectors.yaml
```

## Extending

See [Plugin Guide](docs/PLUGIN_GUIDE.md) for:
- [Adding a Model Adapter](docs/PLUGIN_GUIDE.md#adding-a-model-adapter)
- [Adding a SIEM Connector](docs/PLUGIN_GUIDE.md#adding-a-siem-connector)
- [Adding a Scanner](docs/PLUGIN_GUIDE.md#adding-a-scanner)
- [Adding an Interpreter](docs/PLUGIN_GUIDE.md#adding-an-interpreter)

## Known Limitations

- Scanners require white-box access (gradients/activations) — work best with `provider=local` or HuggingFace local models
- Text model adversarial attacks need embedding-space perturbations (token IDs are discrete)
- Integrated Gradients on text requires access to embedding layer
- Large model audits can be slow — batch mode coming in v0.2.0
- TensorFlow support planned

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [Plugin Guide](docs/PLUGIN_GUIDE.md).

## License

MIT License — see [LICENSE](LICENSE).