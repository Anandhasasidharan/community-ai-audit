# Architecture

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI / API / Library                       │
│                         Entry Point                         │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      AuditEngine                             │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Load   │→ │  Scan    │→ │ Interpret│→ │  Report  │  │
│  │  Model  │  │          │  │          │  │          │  │
│  └─────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                              │                               │
│                      ┌──────────┐                           │
│                      │ Connectors│                           │
│                      │ Push to SIEM│                         │
│                      └──────────┘                           │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Plugin Registry                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Adapters │  │ Scanners │  │Interpreters│ │Reporters │  │
│  │(6 built)│  │(3 built) │  │(2 built) │  │(1 built) │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### AuditEngine

The `AuditEngine` is the central orchestrator. It:
1. **Discovers** all available components via the plugin registry
2. **Loads** a model using the appropriate adapter
3. **Scans** for vulnerabilities using registered scanners
4. **Interprets** model behavior using registered interpreters
5. **Reports** findings via registered reporters
6. **Pushes** results to configured SIEM connectors

### Model Adapters

Adapters bridge the framework to any model provider:

| Adapter | Provider | Types | Notes |
|---------|----------|-------|-------|
| `huggingface` | HuggingFace Hub | Text, Image, Multimodal | transformers, diffusers |
| `openai` | OpenAI API | Text | gpt-4o, o1, etc. |
| `anthropic` | Anthropic API | Text | claude-3, etc. |
| `aws_bedrock` | AWS Bedrock | Text, Image | All Bedrock models |
| `local` | PyTorch/TF/ONNX | All | Load from disk, S3, etc. |
| `ollama` | Ollama | Text | Local LLM server |

### SIEM Connectors

Connectors push findings to security platforms:

| Connector | Platform | Batch Size | Auth |
|-----------|----------|------------|------|
| `splunk` | Splunk HEC | 100 | Token |
| `elastic` | Elastic Security | 100 | API Key/Cert |
| `datadog` | Datadog Logs | 100 | API Key |
| `sentinel` | Microsoft Sentinel | 100 | Shared Key |

### Scanners

Scanners detect specific vulnerability types:

| Scanner | Detection | Technique |
|---------|-----------|-----------|
| `backdoor` | Triggered behavior | Activation clustering |
| `adversarial` | FGSM/PGD vulnerability | Gradient-based attacks |

### Interpreters

Interpreters explain model predictions:

| Interpreter | Method | Works With |
|-------------|--------|------------|
| `integrated-gradients` | Path integration | Local models |
| `lime` | Local perturbations | All models |

### Reporters

Reporters format output:

| Reporter | Format | Use Case |
|----------|--------|----------|
| `markdown` | Human-readable | GitHub, docs |
| `json` | Structured data | Integration |
| `html` | Rich web view | Dashboards |
| `sarif` | Industry standard | CI/CD pipelines |

## Plugin Discovery

Plugins are discovered through:

1. **Built-in packages** — modules in `community_ai_audit/plugins/`
2. **Entry points** — packages that expose `community_ai_audit.plugins`
3. **User paths** — directories passed via `--plugin-path` or `COMMUNITY_AI_AUDIT_PLUGIN_PATH`

```python
# Example: Register a plugin via entry points (in setup.py/pyproject.toml)
[project.entry-points."community_ai_audit.plugins"]
my_scanner = "my_package.scanners:MyScanner"
```

## Data Flow

```
┌────────────┐     ┌────────────┐     ┌────────────┐
│   Model    │────→│  Scanner   │────→│ Finding(s) │
│  (adapter) │     │ (plugin)   │     └─────┬──────┘
└────────────┘     └────────────┘           │
                                            ↓
┌────────────┐     ┌────────────┐     ┌────────────┐
│   Input    │────→│ Interpreter│────→│ Attribution│
│  (probe)   │     │  (plugin)  │     └─────┬──────┘
└────────────┘     └────────────┘           │
                                            ↓
                              ┌─────────────────────┐
                              │    AuditSession     │
                              │  (findings + attrs) │
                              └──────────┬──────────┘
                                         │
                              ┌──────────┴──────────┐
                              │                     │
                              ↓                     ↓
                         ┌────────────┐      ┌────────────┐
                         │  Reporter  │      │  Connector │
                         │  (report)  │      │  (push)    │
                         └────────────┘      └────────────┘
```

## Configuration

The engine loads configuration from (in order of precedence):

1. **CLI arguments** — highest priority
2. **Environment variables** — `COMMUNITY_AI_AUDIT_*` prefix
3. **User config** — path passed via `--config`
4. **Default config** — `config/default.yaml` in the package

## Extensibility

Every component is an abstract base class. Adding a new component:

1. **Adapter**: Inherit `ModelAdapter`, implement 6 methods
2. **Connector**: Inherit `SIEMConnector`, implement 5 methods
3. **Scanner**: Inherit `ScannerPlugin`, implement 1 method
4. **Interpreter**: Inherit `InterpreterPlugin`, implement 1 method
5. **Reporter**: Inherit `ReporterPlugin`, implement 1 method

See the individual guides for step-by-step instructions:
- [ADAPTER_GUIDE.md](ADAPTER_GUIDE.md)
- [CONNECTOR_GUIDE.md](CONNECTOR_GUIDE.md)
- [SCANNER_GUIDE.md](SCANNER_GUIDE.md)
- [INTERPRETER_GUIDE.md](INTERPRETER_GUIDE.md)

## Testing Strategy

| Level | Tool | Scope |
|-------|------|-------|
| Unit | unittest | Individual components |
| Integration | unittest + mocks | Scanner + adapter combinations |
| Smoke | CLI | End-to-end with mocked deps |
| Connector tests | unittest + mocks | HTTP retry, validation, DLQ |
| Benchmark | pytest-benchmark | Performance regression |

## Security Considerations

- **No secrets in code**: All credentials via env vars or config files
- **Input validation**: All user inputs validated before model execution
- **Sandboxing**: Scanner probes use synthetic data only
- **Rate limiting**: Built-in retry with exponential backoff
- **Audit trail**: Every finding includes provenance metadata
