<div align="center">
  <h1>🛡️ Community AI Audit</h1>
  <p><strong>Enterprise-Grade AI Security Auditing · Open Source · Community-Driven</strong></p>
  <p>
    <a href="https://pypi.org/project/community-ai-audit/"><img src="https://img.shields.io/pypi/pyversions/community-ai-audit.svg" alt="Python versions"></a>
    <a href="LICENSE"><img src="https://img.shields.io/github/license/anomalyco/community-ai-audit.svg" alt="License"></a>
    <a href="https://pypi.org/project/community-ai-audit/"><img src="https://img.shields.io/pypi/v/community-ai-audit.svg" alt="PyPI"></a>
    <a href="https://github.com/anomalyco/community-ai-audit/actions"><img src="https://img.shields.io/github/actions/workflow/status/anomalyco/community-ai-audit/ci.yml?branch=main" alt="CI"></a>
    <a href="https://codecov.io/gh/anomalyco/community-ai-audit"><img src="https://img.shields.io/codecov/c/github/anomalyco/community-ai-audit" alt="Coverage"></a>
    <a href="https://github.com/anomalyco/community-ai-audit/pkgs/container/community-ai-audit"><img src="https://img.shields.io/github/v/release/anomalyco/community-ai-audit?label=ghcr&logo=docker" alt="GHCR"></a>
  </p>
  <br>
</div>

**Community AI Audit** is a unified security auditing platform for AI/ML models. It provides vulnerability scanning, red team attack simulations, mechanistic interpretability analysis, alignment auditing, and a unified 7-dimension scoring engine — all from a single CLI.

---

## 🔍 What You Can Do

| Use Case | What It Solves |
|----------|----------------|
| **🛡️ Vulnerability Scanning** | Detect adversarial susceptibility, backdoors, prompt injection, data extraction, toxicity, watermark detectability |
| **⚔️ Red Team Testing** | Simulate jailbreak, multi-turn, obfuscation, roleplay, and tool exploitation attacks |
| **🧠 Mechanistic Interpretability** | Probe representations, attention patterns, feature attribution, and layer behavior |
| **🎯 Alignment Auditing** | Measure sycophancy, preference drift, value alignment, and objective robustness |
| **📊 Unified Scoring** | Aggregate 7 security dimensions into a single risk score with configurable weights |
| **📈 Trend Tracking** | Monitor score evolution across time and detect regressions |
| **📡 SIEM Integration** | Push findings to Splunk, Elastic, Datadog, Sentinel, and 9+ other platforms |

---

## ⚡ Quickstart

```bash
pip install community-ai-audit

# Discover available plugins
community-ai-audit discover

# Scan a model
community-ai-audit scan distilgpt2 --provider huggingface --profile quick

# Full audit with SIEM push
community-ai-audit audit meta-llama/Llama-3-8B-Instruct \
  --provider huggingface --profile standard \
  --connectors splunk elastic

# Red team attack simulation
community-ai-audit redteam gpt-4 --provider openai

# Alignment auditing
community-ai-audit alignment claude-3-opus --provider anthropic

# Compute unified 7-dimension score
community-ai-audit audit-score \
  --scan scan_results.json \
  --redteam redteam_results.json \
  --alignment alignment_results.json
```

---

## 🧩 Capabilities

### Model Support — 9 Adapters

| Provider | Adapter | Auto-Detect |
|----------|---------|-------------|
| HuggingFace | `huggingface` | `*/*` or `llama*` |
| OpenAI | `openai` | `gpt-*`, `o1*`, `o3*` |
| Anthropic | `anthropic` | `claude-*` |
| AWS Bedrock | `aws_bedrock` | — |
| Local (PyTorch/TF/ONNX) | `local` | Path/URI/`*.pt`/`*.onnx` |
| Ollama | `ollama` | `name:tag` (no `/`) |
| Replicate | `replicate` | — |
| VertexAI | `vertexai` | — |
| Groq | `groq` | — |

### Security Scanning — 7 Scanners

| Scanner | What It Detects | Technique |
|---------|----------------|-----------|
| `adversarial` | FGSM/PGD perturbation susceptibility | Gradient-based attacks |
| `backdoor` | Triggered malicious behavior | Activation clustering |
| `prompt_injection` | Injection vulnerabilities | Heuristic pattern matching |
| `data_extraction` | Training data / secret extraction | Response entropy analysis |
| `toxicity` | Toxic / biased outputs | Keyword + classifier scoring |
| `watermark` | Watermark detectability | Statistical pattern analysis |
| `dsl` | User-defined rules | YAML rule engine |

### Red Team — 5 Attack Scanners

| Scanner | Attack Surface | Evaluation |
|---------|---------------|------------|
| `jailbreak` | 20 known jailbreak prompts | Refusal vs success pattern matching |
| `multi_turn_attack` | 10 two-turn conversation attacks | Suspicious-keyword breach detection |
| `prompt_obfuscation` | 10 obfuscated variants (base64, leetspeak) | Harmful-keyword matching |
| `roleplay_attack` | 15 roleplay scenarios (DAN, character shells) | Refusal vs engagement patterns |
| `tool_exploitation` | 10 tool-misuse prompts | Exploit-keyword detection |

### Mechanistic Interpretability — 5 Analyzers

| Analyzer | Probes | What It Measures |
|----------|--------|------------------|
| `activation_probes` | 5 probe inputs | Response quality, SNR estimate |
| `representation_analysis` | 8 probes, 4 pairs | Jaccard differentiation, vocabulary size |
| `attention_head_analysis` | 5 syntactic probes | Attention complexity estimate |
| `feature_attribution` | 5 sentiment inputs | Word-level importance, sentiment match |
| `layer_analysis` | 3 open-ended probes | Depth estimation, complexity distribution |

### Alignment Auditing — 4 Scanners

| Scanner | Prompts | What It Detects |
|---------|---------|-----------------|
| `sycophancy` | 5 agree + 5 disagree | Stance-sycophancy (rubber-stamping) |
| `preference_drift` | 5 cores × 3 variants | Sentiment inconsistency across paraphrases |
| `value_alignment` | 8 probes across 6 values | Refusal of harmful, encouragement of prosocial |
| `objective_robustness` | 3 objectives × 4 prompts | Refusal-pattern violations per objective |

### Scoring — 7 Dimensions

```
┌─────────────────────────────────────────────┐
│           Unified Audit Score                │
├──────────────┬──────────────────────────────┤
│ Security     │   ████████████████░░ 82.0     │
│ Reliability  │   ██████████████░░░░ 72.0     │
│ Compliance   │   ██████████████████ 90.0     │
│ Agent Risk   │   ████████████████░░ 80.0     │
│ Alignment    │   ████████████████░░ 85.0     │
│ Red Team     │   ████████████░░░░░░ 60.0     │
│ Interpretability │ ████████████░░░░░░ 65.0   │
├──────────────┴──────────────────────────────┤
│ Overall: 77.6 (Good)                        │
│ Weights: security=0.2, reliability=0.1, ... │
└─────────────────────────────────────────────┘
```

### Executive Dashboard

Real-time HTML dashboard served via `dashboard_v2/server.py`:
- 7 color-coded score cards (critical → excellent)
- JSON overlay endpoint for programmatic updates
- Configurable refresh interval
- Responsive CSS grid layout

---

## 🔧 Installation

```bash
# Core (numpy, pyyaml, scikit-learn)
pip install community-ai-audit

# Optional extras
pip install community-ai-audit[torch]      # Torch-based scanners
pip install community-ai-audit[scheduler]  # Cron scheduling
pip install community-ai-audit[hf]         # HuggingFace transformers
pip install community-ai-audit[tf]         # TensorFlow

# Development
git clone https://github.com/anomalyco/community-ai-audit
cd community-ai-audit
pip install -e .[dev]
```

---

## 💻 CLI Reference

| Command | Description |
|---------|-------------|
| `scan <model> -p <provider>` | Run vulnerability scanners |
| `interpret <model> -p <provider>` | Run interpretability methods |
| `audit <model> -p <provider>` | Full pipeline: scan + interpret + report + push |
| `redteam <model> -p <provider>` | Red team attack simulations |
| `mechinterp <model> -p <provider>` | Mechanistic interpretability analysis |
| `alignment <model> -p <provider>` | Alignment auditing |
| `audit-score` | Compute unified 7-dimension score |
| `discover` | List all discovered plugins |
| `schedule add/list/remove/run` | Manage recurring audits |

Exit codes: `0` = ok, `1` = HIGH/MEDIUM findings, `2` = CRITICAL findings.

---

## 🤖 CI/CD Integration

### GitHub Action

Add to `.github/workflows/audit.yml`:

```yaml
jobs:
  audit:
    steps:
      - uses: anomalyco/community-ai-audit/.github/actions/audit@main
        with:
          model: distilgpt2
          provider: huggingface
          profile: quick
          threshold: medium
```

### Pre-commit (manual)

```yaml
repos:
  - repo: https://github.com/anomalyco/community-ai-audit
    rev: v0.6.0
    hooks:
      - id: community-ai-audit-scan
```

### Docker

```bash
docker pull ghcr.io/anomalyco/community-ai-audit:latest
docker run ghcr.io/anomalyco/community-ai-audit audit distilgpt2 --provider huggingface --profile quick
```

---

## 📚 Documentation

| Resource | Description |
|----------|-------------|
| [Architecture & Reference](docs/ARCHITECTURE.md) | Full component docs, API, CLI, config, deployment |
| [Plugin Guide](docs/PLUGIN_GUIDE.md) | Writing custom adapters, scanners, interpreters |
| [Scanner Guide](docs/SCANNER_GUIDE.md) | Details on each vulnerability scanner |
| [Adapter Guide](docs/ADAPTER_GUIDE.md) | Details on each model adapter |
| [Connector Guide](docs/CONNECTOR_GUIDE.md) | SIEM and storage connector details |
| [Red Team](docs/ARCHITECTURE.md#pluginsredteam--red-team-testing-5-scanners) | Attack framework and scanner reference |
| [Mech Interp](docs/ARCHITECTURE.md#pluginsmechinterp--mechanistic-interpretability-5-analyzers) | Analyzer reference and methodology |
| [Alignment](docs/ARCHITECTURE.md#pluginsalignment--alignment-auditing-4-scanners) | Alignment scanner reference |
| [Scoring Engine](docs/ARCHITECTURE.md#corescoring--unified-scoring-engine) | 7-dimension scoring details |
| [Dashboard](docs/ARCHITECTURE.md#dashboard_v2--executive-dashboard) | Executive dashboard server |

---

## 📋 Configuration

```yaml
cache:
  enabled: true
  max_size: 1000
  ttl_seconds: 3600

scanners:
  adversarial:
    num_samples: 32
    pgd_steps: 10
  backdoor:
    sample_size: 128

connectors:
  splunk:
    url: "${SPLUNK_URL}"
    token: "${SPLUNK_TOKEN}"
  elastic:
    url: "${ELASTIC_URL}"
    api_key: "${ELASTIC_API_KEY}"
```

Config values can also be set via environment variables: `COMMUNITY_AI_AUDIT_CONNECTORS_SPLUNK_URL`.

Precedence (lowest → highest): `default.yaml` → `--config PATH` → env vars → CLI args.

### API Key Safety

1. `COMMUNITY_AI_AUDIT_API_KEY` env var **(recommended)**
2. `--api-key-file PATH` (reads from file, not visible in ps)
3. `--api-key VALUE` (⚠️ visible in process list)

---

## 🚀 Deployment

```bash
# Docker
docker build -t community-ai-audit .
docker run -v $(pwd)/config:/app/config community-ai-audit scan model.pt -p local

# Docker Compose
docker-compose up -d

# Helm (Kubernetes)
helm install community-ai-audit ./charts/community-ai-audit

# Air-Gapped
./scripts/airgap-bundle.sh   # On connected machine
./scripts/offline-install.sh  # On air-gapped machine
```

---

## 🧪 Testing

```bash
# All tests (no torch/croniter needed)
pytest tests/

# With coverage
pytest --cov=community_ai_audit tests/
```

**508+ tests** covering unit, integration, CLI, connectors, red team, mechanistic interpretability, alignment, trend tracking, and drift analysis.

---

## 🤝 Contributing

We welcome contributions! See our [Plugin Guide](docs/PLUGIN_GUIDE.md) to get started writing custom scanners, adapters, or connectors.

---

## 📄 License

[MIT](LICENSE) © Anomaly Co.
