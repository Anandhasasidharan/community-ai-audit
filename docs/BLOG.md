# Building Community AI Audit: A Plugin-Driven Security Tool for the AI Era

**How we built an open-source, community-driven AI security audit tool with plug-and-play model adapters and SIEM connectors — from zero to PyPI in four phases.**

---

AI models are being deployed everywhere — in chatbots, code assistants, medical diagnosis, financial analysis. But unlike traditional software, there's no standard way to security-audit them. Each model provider has its own API, each SIEM platform speaks a different protocol, and every vulnerability scanner targets a specific attack surface.

At Community AI Audit, we set out to build something different: a **plugin-driven framework** where anyone can add a new model provider, scanner, or SIEM connector in about 30 minutes — without touching the core engine.

Here's the story of how we built it.

---

## The Problem

Organizations auditing AI models today face three challenges:

1. **Vendor lock-in** — OpenAI's safety tools don't work on Anthropic's models. Splunk's AI features don't integrate with Elastic.
2. **No standard workflow** — Every audit is a bespoke script that works for one model, one scanner, one report format.
3. **Low discoverability** — Great scanning techniques exist in academic papers but never make it into production tools.

We wanted to build a tool that treats AI security like the ecosystem it should be: **plug-and-play, community-driven, and extensible by design**.

---

## Phase 0: The Scaffold — Interfaces Define Everything

Before writing a single adapter or scanner, we defined the **contracts**. Every component in Community AI Audit implements an abstract base class:

```python
class ModelAdapter(ABC):
    @abstractmethod
    def load_model(self, model_id: str, **kwargs) -> Any: ...
    @abstractmethod
    def predict(self, model: Any, inputs: Any, **kwargs) -> Any: ...

class ScannerPlugin(ABC):
    @abstractmethod
    def scan(self, model: Any, adapter: ModelAdapter, probe_data: Any) -> ScanResult: ...

class SIEMConnector(ABC):
    @abstractmethod
    def connect(self, config: Dict[str, Any]) -> None: ...
    @abstractmethod
    def send_events(self, events: List[Dict]) -> str: ...
```

These interfaces sit in a shared registry that auto-discovers all components:

```python
from community_ai_audit.core.registry import adapters, connectors, plugins

# Discover all built-in + pip-installed components
adapters.discover()  # → 6 adapters found
connectors.discover()  # → 4 connectors found
plugins.discover()  # → 5 plugins found
```

**Key decision**: A centralized registry at package level. This means adding a new component is as simple as writing one class and registering it — no changes to the core engine. The downside is global state, which we mitigate with `clear()` and `reset()` methods.

---

## Phase 1: Core E2E — From Model to Report

With interfaces in place, we built the **AuditEngine** — the orchestrator that wires everything together:

```
Input → Load Model → Scan → Interpret → Report → Push to SIEM
```

### The Adapter Layer (6 providers)

Each adapter wraps a model provider's SDK behind a common interface:

| Adapter | Backend | Lines of Code |
|---------|---------|--------------|
| HuggingFace | transformers | 141 |
| OpenAI | openai SDK | 69 |
| Anthropic | anthropic SDK | 68 |
| AWS Bedrock | boto3 | 87 |
| Local | PyTorch/TF | 140 |
| Ollama | requests | 69 |

The `huggingface` adapter is the most complex — it supports text, image, and multimodal models, plus hooks for gradient computation needed by scanners. The `ollama` adapter is the simplest — it's just HTTP POST calls to a local server.

### The Scanner Layer (2 built-in)

We built two scanners that demonstrate the range of what's possible:

- **Backdoor scanner** — Uses activation clustering to detect triggered behavior in neural networks. If certain neurons fire differently on inputs with a specific trigger pattern, that's a backdoor signal.
- **Adversarial scanner** — Runs FGSM and PGD attacks to measure robustness. If small perturbations flip predictions, the model is vulnerable.

Both scanners work with any adapter that provides gradient access (local and HuggingFace models).

### The Reporter Layer (3 formats)

Reports come in Markdown (human-readable), JSON (machine-readable), and HTML (dashboard-ready). An AuditSession aggregates all findings with risk scoring:

```python
session = AuditSession(
    model_id="meta-llama/Llama-3-8B-Instruct",
    scan_results=[...],
    interpret_results=[...]
)
session.risk_score  # → 42.5/100 (weighted blend of all scanners)
```

---

## Phase 2: Connectors — Pushing to SIEM Platforms

Security findings are useless if they stay in a JSON file. We built connectors that push audit results into production SIEM pipelines:

| Connector | Platform | Protocol | Key Engineering Challenge |
|-----------|----------|----------|--------------------------|
| Splunk | HEC | HTTP POST | Batched events with retry |
| Elastic | Bulk API | HTTP POST | NDJSON format, scroll pagination |
| Datadog | Logs API | HTTP POST | Rate limiting, 5MB payload limit |
| Sentinel | Log Analytics | HTTP POST | HMAC-SHA256 signature, workspace-level throttling |

### The Retry Utility

Every connector had to deal with network failures, rate limits, and timeouts. Rather than implementing retry logic four times, we built a shared **exponential backoff with jitter** utility:

```python
@retry(max_attempts=5, base_delay=1.0, max_delay=60.0)
def send_to_splunk(self, payload):
    response = requests.post(url, data=payload, headers=headers)
    if response.status_code == 429:  # Rate limited
        raise RetryableError("rate limited")
    return response
```

### Dead-Letter Queue

When events fail after all retries, they're written to a DLQ log instead of being silently dropped. This was a deliberate trade-off: reliability over throughput, which is appropriate for security audit data.

### Event Schema Validation

Different connectors expected different event formats. We added a `validate_events()` function in the base connector that checks required fields (`title`, `severity`) and normalizes values before dispatch.

---

## Phase 3: Documentation & Onboarding

A framework is only as good as its onboarding experience. We wrote four step-by-step guides, each designed to be completable in around 30 minutes:

| Guide | What You Build | Files Touched |
|-------|---------------|---------------|
| ADAPTER_GUIDE.md | DummyHTTP adapter | 1 file, ~70 lines |
| SCANNER_GUIDE.md | Variance scanner | 1 file, ~50 lines |
| CONNECTOR_GUIDE.md | File-based connector | 1 file, ~60 lines |
| INTERPRETER_GUIDE.md | Top-feature interpreter | 1 file, ~50 lines |

Each guide follows the same pattern:

1. Pick a name
2. Inherit the right base class
3. Implement the required methods
4. Register with the registry
5. Test with the CLI

We also documented our **engineering tradeoffs** in `docs/DECISIONS.md` — why we chose centralized retry over per-connector logic, why we use `Any` return types instead of generics, and why we accept deprecation warnings for now.

---

## Phase 4: Tests, CI, and Release

### Test Suite (48 tests, all passing)

```
tests/
├── test_smoke.py           # Basic import and CLI smoke tests
├── test_cli.py             # CLI command parsing and routing
├── test_core.py            # Core interfaces and data structures
├── test_registry.py        # Plugin discovery and registration
├── test_audit_engine.py    # AuditEngine end-to-end flows
├── test_connectors_smoke.py # Connector initialization (mocked)
├── test_retry.py           # Retry/backoff utility
```

### CI Pipeline (GitHub Actions)

Every push runs:

1. **Ruff** — lint all source files
2. **Black** — enforce consistent formatting
3. **Mypy** — type checking
4. **Bandit** — security scanning
5. **pip-audit** — dependency vulnerability audit
6. **pytest-cov** — 48 tests with coverage reporting
7. **Build + validate** — package installs cleanly in isolated venv
8. **Publish** — automated release to TestPyPI and PyPI on tags

### Release Workflow

We use `release-please` for automated changelog generation. When a PR is merged to master with conventional commits:

1. Release-please opens a "Release vX.Y.Z" PR
2. Merging it creates a GitHub release + `vX.Y.Z` tag
3. The tag triggers PyPI publish

---

## Key Design Decisions

### Why Plug-and-Play?

Most AI security tools lock you into a specific model provider. We wanted to decouple the scanning logic from the model access — the same backdoor scanner should work on a local PyTorch model and an OpenAI API endpoint.

**Trade-off**: Slightly more boilerplate for simple use cases, but massive gains in extensibility.

### Why String-Based Forward References?

The `ReportGenerator` needs to reference `AuditSession` from `core/audit.py`, but importing it directly creates a circular dependency. We use `TYPE_CHECKING` guard plus `from __future__ import annotations`.

**Trade-off**: Small complexity at import time. Clean type hints without runtime circular imports.

### Why datetime.utcnow() Warnings Exist

Python 3.12 deprecated `utcnow()`. We accept the warning for now to keep the codebase simple and will migrate in v0.2.0. Low priority.

---

## What We'd Do Differently

Looking back, there are things we'd improve:

1. **More aggressive testing early** — Connector tests with real credentials would have caught edge cases earlier
2. **TypeVar for adapter return types** — We use `Any` everywhere, sacrificing type safety for simplicity
3. **Async from day one** — Connector dispatch and model inference would benefit from async, but adding it now is a breaking change
4. **Better Windows support** — The CLI uses Unicode box-drawing characters that break on Windows cmd

---

## What's Next

The roadmap covers v0.2 through v0.5:

- **v0.2.0** — Performance benchmarks, caching, batch scan mode, parallel dispatch
- **v0.3.0** — More model providers (Google Vertex, Groq), more SIEMs (QRadar, Sumo)
- **v0.4.0** — Advanced scanners (prompt injection, memorization, bias)
- **v0.5.0** — Kubernetes deployment, Docker compose, air-gapped install, scheduled audits

---

## Try It Yourself

```bash
pip install community-ai-audit

# Discover all components
community-ai-audit discover

# Full audit (requires a model)
community-ai-audit audit my_model.pt --provider local \
  --scanners backdoor adversarial \
  --interpreters integrated-gradients \
  --probe-file probes.json
```

Or contribute a new scanner, adapter, or connector — the guides are designed to take about 30 minutes.

---

*Community AI Audit is open-source under MIT. Contribute at [github.com/Anandhasasidharan/community-ai-audit](https://github.com/Anandhasasidharan/community-ai-audit).*
