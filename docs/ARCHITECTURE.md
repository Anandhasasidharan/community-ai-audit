# Community AI Audit — Architecture & Reference

## Overview

Community AI Audit is a plug-and-play security audit framework for AI/ML models.
It supports any model provider (HuggingFace, OpenAI, Anthropic, Ollama, AWS Bedrock, Replicate, VertexAI, Groq, local files),
any vulnerability scanner (7 built-in), any interpretability method (2 built-in),
red team attack frameworks (5 built-in), mechanistic interpretability analyzers (5 built-in),
alignment auditing scanners (4 built-in), and any SIEM/security tool (13+ connectors).
Results can be exported as Markdown, HTML, JSON, pushed to a 7-dimension executive dashboard,
or forwarded to Splunk, Elastic, Datadog, Sentinel, QRadar, LogRhythm, SumoLogic, Webhook,
Pinecone, Weaviate, S3, GCS, or Azure Blob Storage.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Entry Point                               │
│  CLI (community-ai-audit) / Python Library / Scheduled Runner │
└─────────────────────────┬────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────┐
│                       AuditEngine                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ discover │→ │load_model│→ │  audit   │→ │generate_ │    │
│  │          │  │ (adapter)│  │scan+interp│  │ report   │    │
│  └──────────┘  └──────────┘  └────┬─────┘  └──────────┘    │
│                                   │                          │
│                            ┌──────▼──────┐                  │
│                            │  Connectors  │                  │
│                            │ (push results│                  │
│                            │  to SIEM/S3  │                  │
│                            │  etc.)       │                  │
│                            └─────────────┘                  │
└──────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────┐
│                     Plugin Registry + Scoring                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Adapters │  │ Scanners │  │Interpreters│ │  Red     │    │
│  │  (9)     │  │  (7)     │  │  (2)      │  │  Team    │    │
│  │          │  │          │  │           │  │  (5)     │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Mech    │  │Alignment │  │Connectors│  │ Scoring  │    │
│  │  Interp  │  │  (4)     │  │ (13+)    │  │ Engine   │    │
│  │  (5)     │  │          │  │ SIEM+    │  │ (7 dims) │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│  ┌──────────┐                                                │
│  │Reporters │                                                │
│  │  (3)     │                                                │
│  └──────────┘                                                │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Model ──→ Scanner ──→ Finding(s)
Input ──→ Interpreter ──→ Attribution(s)
Model ──→ Red Team Scanner ──→ AttackResult(s)
Model ──→ MechInterp Analyzer ──→ Analysis Result(s)
Model ──→ Alignment Scanner ──→ AlignmentResult(s)
              ↓
        AuditSession ──→ ScoringEngine ──→ 7-Dimension RiskScore
              ↓
        Dashboard (dashboard_v2) / Reporter ──→ Report
              ↓
        Connector ──→ SIEM / S3 / Vector DB / Webhook
```

---

## Features

| Area | Feature | Details |
|------|---------|---------|
| **Model Support** | 9 adapters | HuggingFace, OpenAI, Anthropic, AWS Bedrock, Local (PyTorch/TF/ONNX), Ollama, Replicate, VertexAI, Groq |
| **Vulnerability Scanning** | 7 scanners | adversarial, backdoor, prompt_injection, data_extraction, toxicity, watermark, dsl |
| **Interpretability** | 2 interpreters | integrated-gradients, lime |
| **Red Team Testing** | 5 scanners | jailbreak, multi_turn_attack, prompt_obfuscation, roleplay_attack, tool_exploitation |
| **Mechanistic Interpretability** | 5 analyzers | activation_probes, representation_analysis, attention_head_analysis, feature_attribution, layer_analysis |
| **Alignment Auditing** | 4 scanners | sycophancy, preference_drift, value_alignment, objective_robustness |
| **Scoring Engine** | 7 dimensions | security, reliability, compliance, agent_risk, alignment, red_team, interpretability |
| **Executive Dashboard** | dashboard_v2 | Live 7-dimension score cards, configurable weights, JSON overlay |
| **Reporting** | 5 reporters | markdown, html, json/dashboard, via CLI (redteam/mechinterp/alignment JSON/table) |
| **SIEM Connectors** | 6+ | Splunk, Elastic, Datadog, Microsoft Sentinel, QRadar, LogRhythm, SumoLogic, Webhook |
| **Vector DB / Storage** | 5 | Pinecone, Weaviate, S3, GCS, Azure Blob |
| **Scheduling** | cron-based | Add/list/remove/run schedules via `community-ai-audit schedule` |
| **RBAC** | opt-in | Role-based access control via `--user` |
| **Caching** | LRU+TTL | ModelCache with configurable size and expiry |
| **Diff** | Audit comparison | Compare two AuditSessions to see new/resolved/changed findings |
| **Batch Scanning** | N/A | Process probes in configurable batch sizes |
| **Parallel Dispatch** | N/A | Push to multiple connectors concurrently |
| **YAML DSL** | Custom scanners | Define scanners in YAML without writing Python |
| **Deployment** | Docker / Helm / Air-gap | Dockerfile, docker-compose.yml, Helm chart, airgap-bundle/offline-install scripts |

---

## Core Components

### `core/audit.py` — AuditEngine

The central orchestrator. All public methods:

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(config_path=None, extra_plugin_paths=None, discovery_on_init=True)` | Load config, init cache, optionally discover plugins |
| `discover` | `() → None` | Discover all adapters, connectors, and plugins via the registry |
| `load_model` | `(model_id, provider=None, adapter_config=None, **model_kwargs) → Any` | Auto-detect or select provider, connect adapter, load model, wrap predict with cache |
| `scan` | `(scanners=None, config_overrides=None) → List[ScanResult]` | Run selected (or all) scanners on the loaded model |
| `interpret` | `(inputs, interpreters=None, targets=None, config_overrides=None) → List[InterpretationResult]` | Run selected (or all) interpreters on given inputs |
| `batch_scan` | `(probe_inputs, scanners=None, config_overrides=None, batch_size=1) → List[ScanResult]` | Run scanners over batches of probe inputs |
| `audit` | `(scanners=None, interpreters=None, inputs=None, connectors=None, connector_configs=None, config_overrides=None, run_metadata=None, parallel_connectors=False, connector_max_workers=4) → AuditSession` | Full pipeline: scan + interpret + push to connectors |
| `connect_siem` | `(name, config) → SIEMConnector` | Connect to a SIEM by name |
| `connect_security_tool` | `(name, config) → SecurityToolConnector` | Connect to a security tool by name |
| `generate_report` | `(session, format='markdown') → str` | Generate report from an AuditSession |
| `enable_cache` | `(enabled=True, max_size=None, ttl_seconds=None) → None` | Toggle / reconfigure prediction cache |
| `clear_cache` | `() → None` | Clear prediction cache |
| `list_capabilities` | `() → Dict[str, List[str]]` | Return discovered adapters, connectors, scanners, interpreters, reporters |

#### AuditSession

Container returned by `audit()`:

| Property/Method | Type | Description |
|-----------------|------|-------------|
| `session_id` | `str` | Unique session ID |
| `model_id` | `Optional[str]` | Model that was audited |
| `adapter_name` | `Optional[str]` | Adapter used |
| `started_at` | `datetime` | Start time |
| `completed_at` | `Optional[datetime]` | End time |
| `duration_seconds` | `float` | Duration |
| `scan_results` | `List[ScanResult]` | All scanner results |
| `interpret_results` | `List[InterpretationResult]` | All interpreter results |
| `connector_results` | `Dict[str, Any]` | Per-connector push status |
| `metadata` | `Dict[str, Any]` | Optional run metadata |
| `total_findings` | `int (property)` | Sum of findings across scanners |
| `highest_severity` | `Severity (property)` | Most severe finding level |
| `to_dict()` | `Dict[str, Any]` | Serialize entire session |
| `summary()` | `str` | One-line human-readable summary |

---

### `core/interfaces.py` — Abstract Base Classes

| Interface | Methods | Purpose |
|-----------|---------|---------|
| `ModelAdapter` | `connect`, `disconnect`, `get_model`, `predict`, `get_input_spec`, `supports_model_type` | Base for all model providers |
| `TextModelAdapter` | + `tokenize`, `generate`, `get_logits`, `get_attention_weights` | Text/LLM specialization |
| `ImageModelAdapter` | + `preprocess_image`, `get_layer_activations` | Image model specialization |
| `MultiModalAdapter` | + `tokenize`, `preprocess_image` | Multimodal specialization |
| `SIEMConnector` | `connect`, `disconnect`, `send_event`, `send_batch`, `query` | Security event platform integration |
| `SecurityToolConnector` | `connect`, `disconnect`, `push_finding`, `pull_context` | Security tool integration |
| `ThreatIntelConnector` | + `enrich_finding`, `lookup_ioc` | Threat intelligence feeds |
| `ScannerPlugin` | `scan` + `get_config_schema` | Vulnerability scanners |
| `InterpreterPlugin` | `interpret` + `get_config_schema` | Interpretability methods |
| `ReporterPlugin` | `render` | Report format plugins |

#### Data Classes

| Class | Fields | Description |
|-------|--------|-------------|
| `Finding` | `title`, `description`, `severity`, `evidence`, `cwe_id`, `mitre_id`, `nist_id`, `confidence`, `recommendation`, `raw_data` | A single vulnerability finding |
| `ScanResult` | `scanner_name`, `scanner_version`, `findings`, `metadata`, `error` | Output of one scanner run |
| `InterpretationResult` | `interpreter_name`, `interpreter_version`, `attributions`, `visualization`, `summary`, `metadata`, `error` | Output of one interpreter run |

#### Enums

| Enum | Values |
|------|--------|
| `ModelType` | `TEXT`, `IMAGE`, `MULTIMODAL`, `EMBEDDING`, `UNKNOWN` |
| `Severity` | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`, `UNKNOWN` |

---

### `core/registry.py` — Plugin Registry

The registry auto-discovers components from three sources:

1. **Built-in packages** — `community_ai_audit/adapters/`, `community_ai_audit/connectors/`, `community_ai_audit/plugins/scanners/`, `community_ai_audit/plugins/interpreters/`, `community_ai_audit/plugins/reporters/`
2. **Entry points** — packages exposing `community_ai_audit.plugins`, `community_ai_audit.adapters`, or `community_ai_audit.connectors`
3. **User paths** — directories passed via `extra_plugin_paths` or `COMMUNITY_AI_AUDIT_PLUGIN_PATH`

Three global registries are exported:

```python
from community_ai_audit.core.registry import adapters, connectors, plugins
```

Each registry exposes:

| Method | Description |
|--------|-------------|
| `discover()` | Scan all sources and register components |
| `list_available()` | Return list of registered component names |
| `get(name, config=None)` | Get component instance by name, optionally with config |

`plugins` additionally has:

| Method | Description |
|--------|-------------|
| `list_scanners()` | Names of all discovered scanner plugins |
| `list_interpreters()` | Names of all discovered interpreter plugins |
| `list_reporters()` | Names of all discovered reporter plugins |
| `scanners.get(name)` | Get scanner instance by name |
| `interpreters.get(name)` | Get interpreter instance by name |
| `reporters.get(name)` | Get reporter instance by name |

---

### `adapters/` — Model Providers (9)

| File | Class | Provider | Auto-detect pattern |
|------|-------|----------|-------------------|
| `huggingface_adapter.py` | `HuggingFaceAdapter` | HuggingFace / transformers | `*/*` or `llama*` |
| `openai_adapter.py` | `OpenAIAdapter` | OpenAI API | `gpt-*`, `o1*`, `o3*` |
| `anthropic_adapter.py` | `AnthropicAdapter` | Anthropic API | `claude-*` |
| `aws_bedrock_adapter.py` | `AWSBedrockAdapter` | AWS Bedrock | N/A |
| `local_adapter.py` | `LocalAdapter` | PyTorch/TF/ONNX from disk/S3/URL | Path/URI/`*.pt`/`*.pth`/`*.onnx`/`*.safetensors` |
| `ollama_adapter.py` | `OllamaAdapter` | Ollama local server | `name:tag` (no `/`) |
| `replicate_adapter.py` | `ReplicateAdapter` | Replicate API | N/A |
| `vertexai_adapter.py` | `VertexAIAdapter` | Google VertexAI | N/A |
| `groq_adapter.py` | `GroqAdapter` | Groq API | N/A |

Common adapter interface (via `ModelAdapter`):

```python
adapter.connect(config: Dict)
adapter.disconnect()
model = adapter.get_model(model_id: str, **kwargs)
output = adapter.predict(model, inputs, **kwargs)
spec = adapter.get_input_spec(model)
adapter.supports_model_type(model_type: ModelType) -> bool
```

---

### `connectors/` — SIEM & Storage Integrations (13+)

| File | Class | Type | `send_batch` | `send_event` | `push_finding` | `query` |
|------|-------|------|:---:|:---:|:---:|:---:|
| `splunk_connector.py` | `SplunkConnector` | SIEM | ✓ | ✓ | | ✓ |
| `elastic_connector.py` | `ElasticConnector` | SIEM | ✓ | ✓ | | ✓ |
| `datadog_connector.py` | `DatadogConnector` | SIEM | ✓ | ✓ | | ✓ |
| `sentinel_connector.py` | `SentinelConnector` | SIEM | ✓ | ✓ | | ✓ |
| `qradar_connector.py` | `QRadarConnector` | SIEM | ✓ | ✓ | | ✓ |
| `logrhythm_connector.py` | `LogRhythmConnector` | SIEM | ✓ | ✓ | | ✓ |
| `sumologic_connector.py` | `SumoLogicConnector` | SIEM | ✓ | ✓ | | ✓ |
| `webhook_connector.py` | `WebhookConnector` | SIEM | ✓ | ✓ | | |
| `pinecone_connector.py` | `PineconeConnector` | Vector DB | ✓ | | ✓ | ✓ |
| `weaviate_connector.py` | `WeaviateConnector` | Vector DB | ✓ | | ✓ | ✓ |
| `s3_connector.py` | `S3Connector` | Storage | | ✓ | ✓ | |
| `gcs_connector.py` | `GCSConnector` | Storage | | ✓ | ✓ | |
| `azure_blob_connector.py` | `AzureBlobConnector` | Storage | | ✓ | ✓ | |

Every connector implements `connect(config)` and `disconnect()`.

The `retry.py` helper wraps connector calls with exponential backoff.

---

### `plugins/scanners/` — Vulnerability Scanners (7)

| Plugin | Name | What it detects | Technique |
|--------|------|----------------|-----------|
| `adversarial.py` | `adversarial` | Susceptibility to FGSM/PGD attacks | Gradient-based perturbation |
| `backdoor.py` | `backdoor` | Triggered malicious behavior | Activation clustering + outlier detection |
| `prompt_injection.py` | `prompt_injection` | Prompt injection vulnerabilities | Heuristic pattern matching |
| `data_extraction.py` | `data_extraction` | Extraction of training data / secrets | Response entropy + pattern analysis |
| `toxicity.py` | `toxicity` | Toxic / biased output generation | Keyword + classifier-based scoring |
| `watermark.py` | `watermark` | AI-generated content watermark detectability | Statistical pattern analysis (requires torch) |
| `dsl.py` | `dsl` | User-defined YAML DSL scanners | Loads rules from YAML config |

Each scanner subclasses `ScannerPlugin` and implements:
```python
def scan(self, model, adapter: ModelAdapter, config=None) -> ScanResult
```

---

### `plugins/interpreters/` — Interpretability (2)

| Plugin | Name | Method |
|--------|------|--------|
| `integrated_gradients.py` | `integrated-gradients` | Path-integrated gradients (requires torch) |
| `lime.py` | `lime` | Local Interpretable Model-agnostic Explanations |

Each interpreter subclasses `InterpreterPlugin` and implements:
```python
def interpret(self, model, adapter, inputs, target=None, config=None) -> InterpretationResult
```

---

### `plugins/redteam/` — Red Team Testing (5 scanners)

Red team scanners simulate adversarial attacks against LLMs to measure vulnerability to jailbreaking, prompt manipulation, and tool misuse.

| Scanner | File | Attack Surface | Evaluation Method |
|---------|------|----------------|-------------------|
| `JailbreakScanner` | `jailbreak.py` | 20 known jailbreak prompts | Refusal vs success pattern matching |
| `MultiTurnAttackScanner` | `multi_turn.py` | 10 two-turn conversation attacks | Suspicious-keyword breach detection (2nd turn) |
| `PromptObfuscationScanner` | `obfuscation.py` | 10 obfuscated prompt variants (base64, leetspeak, etc.) | Harmful-keyword matching on decoded input |
| `RoleplayAttackScanner` | `roleplay.py` | 15 roleplay scenarios (DAN, character shells) | Refusal vs engagement pattern matching |
| `ToolExploitationScanner` | `exploitation.py` | 10 tool-misuse prompts (syscmd, func injection) | Exploit-keyword detection |

**Framework ABCs** (defined in `base.py`):

| Class | Purpose |
|-------|---------|
| `AttackGenerator` | Generate attack prompts for a given strategy |
| `AttackExecutor` | Execute attacks against a model adapter and collect responses |
| `AttackEvaluator` | Evaluate model responses for signs of successful attack |
| `AttackResult` | Dataclass with `attack_id`, `prompt`, `response`, `success`, `risk_score`, `evidence` |

**Registry** (`__init__.py`):
- `list_redteam_scanners()` → list of all scanner names
- `get_redteam_scanner(name)` → scanner instance
- `run_redteam_scanners(model, adapter, scanner_names=None)` → list of `AttackResult` dicts

All scanners subclass the `RedTeamScanner` ABC and implement:
```python
def run(self, model, adapter) -> AttackResult
```

---

### `plugins/mechinterp/` — Mechanistic Interpretability (5 analyzers)

Mechanistic interpretability analyzers probe model internals to understand representations, attention patterns, feature attribution, and layer behavior — without requiring actual model internals access (works via response analysis).

| Analyzer | File | Probes | What It Measures |
|----------|------|--------|------------------|
| `ActivationProbes` | `activation_probes.py` | 5 probe inputs | Response quality, signal-to-noise ratio estimate |
| `RepresentationAnalysis` | `representation.py` | 8 probes, 4 paired comparisons | Representation differentiation (Jaccard vocabulary overlap), vocabulary size estimate |
| `AttentionHeadAnalysis` | `attention_head.py` | 5 syntactic probes | Attention complexity estimate via input/output token overlap |
| `FeatureAttribution` | `feature_attribution.py` | 5 sentiment inputs | Word-level importance scores, sentiment-match detection |
| `LayerAnalysis` | `layer_analysis.py` | 3 open-ended probes | Depth estimation via output/input length ratios, complexity distribution |

**Framework** (`base.py`):
- `MechanisticInterpreter` ABC with `analyze(model, adapter)` → dict

**Registry** (`__init__.py`):
- `list_mechinterp_analyzers()` → list of all analyzer names
- `get_mechinterp_analyzer(name)` → analyzer instance
- `run_mechinterp_analyzers(model, adapter, analyzer_names=None)` → list of result dicts

---

### `plugins/alignment/` — Alignment Auditing (4 scanners)

Alignment scanners measure whether an LLM's outputs are consistent with intended human values, preferences, and objectives.

| Scanner | File | Prompts | What It Detects |
|---------|------|---------|-----------------|
| `SycophancyScanner` | `sycophancy.py` | 5 agree + 5 disagree prompts | Stance-sycophancy (rubber-stamping user's view) |
| `PreferenceDriftScanner` | `preference_drift.py` | 5 core prompts × 3 variants | Sentiment inconsistency across paraphrased requests |
| `ValueAlignmentScanner` | `value_alignment.py` | 8 probes across 6 values | Refusal of harmful requests, encouragement of prosocial ones |
| `ObjectiveRobustnessScanner` | `objective_robustness.py` | 3 objectives × 4 prompts each | Refusal-pattern violations within an objective |

**Framework** (`base.py`):
- `AlignmentScanner` ABC with `evaluate(model, adapter)` → `AlignmentResult`
- `AlignmentResult` dataclass: `scanner_name`, `alignment_score` (0–100), `confidence` (0–1), `evidence` (list of dicts)

**Registry** (`__init__.py`):
- `list_alignment_scanners()` → list of all scanner names
- `get_alignment_scanner(name)` → scanner instance
- `run_alignment_scanners(model, adapter, scanner_names=None)` → list of result dicts

---

### `core/scoring/` — Unified Scoring Engine

The scoring engine aggregates results from scanners, red team tests, mechanistic interpretability, and alignment audits into a single unified score across 7 dimensions.

| Component | File | Description |
|-----------|------|-------------|
| `RiskScore` | `models.py` | Dataclass with 7 dimension scores + overall + configurable weights |
| `OverallAuditScore` | `models.py` | Simplified audit summary score with `interpret()` method |
| `ScoringEngine` | `engine.py` | Computes dimension scores from result lists, normalizes, applies weights |
| `DEFAULT_WEIGHTS` | `models.py` | `security=0.2, reliability=0.1, compliance=0.1, agent_risk=0.2, alignment=0.2, red_team=0.1, interpretability=0.1` |

**ScoringEngine API**:

| Method | Description |
|--------|-------------|
| `compute(security_results, reliability_results, compliance_results, agent_risk_results, red_team_results, alignment_results, interpretability_results)` | Compute all dimension scores → `RiskScore` |
| `set_weight(dimension, value)` | Update a single weight, auto-normalizes to sum=1.0 |
| `set_weights(dict)` | Update multiple weights at once |
| `weights` | Current weight dict (read-only property) |

**Score interpretation**:

| Range | Label |
|-------|-------|
| 90–100 | Excellent |
| 75–89 | Good |
| 65–74 | Fair |
| 50–64 | Poor |
| 0–49 | Critical |

---

### `dashboard_v2/` — Executive Dashboard

The executive dashboard provides a real-time HTML view of all 7 security dimensions with configurable score weights.

| Component | File | Description |
|-----------|------|-------------|
| `DashboardServer` | `server.py` | HTTP server rendering an HTML dashboard with score cards |
| `ScoreCard` | `server.py` | Visual card component per dimension (color-coded, progress bar) |

**Features**:
- 7 score cards: Agent Risk, Security, Reliability, Compliance, Alignment, Red Team Risk, Interpretability
- Color-coded severity: critical (red), poor (orange), fair (yellow), good (lime), excellent (green)
- Configurable refresh interval
- JSON overlay endpoint for programmatic updates
- Responsive CSS grid layout (`auto-fit`, `minmax(200px, 1fr)`)

**Dashboard API**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Full HTML dashboard page |
| `/scores` | GET | Current scores as JSON |
| `/update` | POST | Update scores programmatically |

---

### `plugins/reporters/` — Report Formats (3)

| Plugin | Name | Format |
|--------|------|--------|
| `markdown.py` | `markdown-reporter` | Markdown |
| `html.py` | `html-reporter` | HTML |
| `dashboard.py` | `json-dashboard-reporter` | JSON (for dashboard consumption) |

Each reporter subclasses `ReporterPlugin` and implements:
```python
def render(self, scan_results, interpret_results, metadata) -> str
```

---

### `reporting/generator.py` — ReportGenerator

Facade that delegates to the appropriate `ReporterPlugin`:

| Method | Description |
|--------|-------------|
| `render_session(session, fmt='markdown') → str` | Render full AuditSession |
| `render_scan_results(results, fmt='markdown') → str` | Render scan results only |
| `render_interpret_results(results, fmt='markdown') → str` | Render interpretation results only |

---

### `cache.py` — ModelCache

Thread-safe LRU cache with TTL for model predictions.

| Method | Description |
|--------|-------------|
| `get(key) → Any` | Retrieve cached value (None if miss/expired) |
| `set(key, value) → None` | Store value, evict LRU if at capacity |
| `clear() → None` | Empty entire cache |
| `invalidate(key) → None` | Remove single entry |
| `make_predict_wrapper(predict_fn) → Callable` | Wrap predict function with caching (keyed by model_id + input) |
| `stats → Dict[str, Any]` | Hit rate, size, evictions |

---

### `diff.py` — AuditDiff

Compare two audit sessions.

| Function | Description |
|----------|-------------|
| `audit_diff(session_a, session_b, match_by='title') → AuditDiff` | Compare sessions and return structured diff |

`AuditDiff` properties: `new_findings`, `resolved_findings`, `changed_findings`, `severity_shifts`, `severity_trend` (improved/worsened/stable), `total_changes`, `summary()`, `to_dict()`.

---

### `core/scheduler.py` — AuditScheduler

Cron-based recurring audit scheduler. Persists schedules to `~/.community-ai-audit/schedules.json`.

| Method | Description |
|--------|-------------|
| `add_schedule(name, cron, model_id, provider, scanners, interpreters, connectors, profile, output_format)` | Register a new cron schedule |
| `remove_schedule(name)` | Remove by name |
| `list_schedules() → List[Dict]` | List all schedules |
| `get_due_schedules(now=None) → List[Tuple]` | Check which schedules are due |
| `mark_run(name)` | Update last_run timestamp |
| `save()` | Persist to disk |
| `run_due(engine, now=None, model_timeout=300, audit_timeout=3600) → List[Dict]` | Execute all due schedules with timeouts |

---

### `core/rbac.py` — Access Control

Opt-in role-based access control. Enabled only when `--user` is provided.

| Class | Description |
|-------|-------------|
| `RBACConfig` | Loads users/roles/permissions from `~/.community-ai-audit/rbac.json` |
| `AccessControl` | `authenticate(user, api_key) → bool`, `require_permission(user, permission) → None` |
| `PermissionError` | Raised on auth/authz failure |

---

## CLI Reference

```
community-ai-audit [--version] [-v] [--config PATH] <command> [options]

Commands:
  scan         Run vulnerability scanners on a model
  interpret    Run interpretability methods on a model
  audit        Run full audit (scan + interpret + report)
  discover     List all discovered plugins and adapters
  schedule     Manage recurring audit schedules
  redteam      Run red team attack simulations
  mechinterp   Run mechanistic interpretability analyzers
  alignment    Run alignment auditing scanners
  audit-score  Compute unified audit score from result files
```

### Global Options

| Flag | Description |
|------|-------------|
| `--version` | Print version |
| `-v` / `--verbose` | DEBUG-level logging |
| `--config PATH` | YAML config file override |

### `scan` — Run vulnerability scanners

```
community-ai-audit scan <model> --provider <provider> [options]
```

| Option | Description |
|--------|-------------|
| `--provider` / `-p` | REQUIRED. huggingface, openai, anthropic, aws_bedrock, local, ollama |
| `--profile` | quick, standard (default), deep, custom |
| `--scanners` / `-s` | Scanner names to run |
| `--connectors` / `-c` | SIEM/connectors to push results |
| `--output` / `-o` | markdown (default), json, html |
| `--save PATH` | Save report to file |
| `--device` | cpu, cuda, mps |
| `--api-key` | API key (visible in ps, warns) |
| `--api-key-file` | Read API key from file |
| `--input-shape JSON` | Adversarial probe shape, e.g. `[32,16]` |
| `--probe-inputs JSON` | Inline probe inputs |
| `--probe-file PATH` | Probe file (.json/.jsonl/.ndjson/.csv) |
| `--user` | RBAC username |
| `--api-key-rbac` | RBAC API key |

Exit codes: 0 = ok, 1 = HIGH/MEDIUM findings, 2 = CRITICAL findings.

### `interpret` — Run interpretability

```
community-ai-audit interpret <model> --provider <provider> [options]
```

| Option | Description |
|--------|-------------|
| `--interpreters` / `-i` | Interpreter names |
| `--input` | Input data (text or image path) |
| `--output` / `-o` | markdown, json, html |
| `--save PATH` | Save report |
| `--device` | cpu, cuda, mps |
| `--api-key` / `--api-key-file` | API key |
| `--user` / `--api-key-rbac` | RBAC |

### `audit` — Full audit (scan + interpret)

```
community-ai-audit audit <model> --provider <provider> [options]
```

Combines all flags from `scan` and `interpret`.

### `redteam` — Run red team attack simulations

```
community-ai-audit redteam <model> --provider <provider> [options]
```

| Option | Description |
|--------|-------------|
| `--scanners` / `-s` | Scanner names to run (default: all) |
| `--output` / `-o` | json (default), table |
| `--save PATH` | Save results to file |
| `--api-key` / `--api-key-file` | API key |

### `mechinterp` — Run mechanistic interpretability

```
community-ai-audit mechinterp <model> --provider <provider> [options]
```

| Option | Description |
|--------|-------------|
| `--analyzers` / `-a` | Analyzer names to run (default: all) |
| `--output` / `-o` | json (default), table |
| `--save PATH` | Save results to file |
| `--api-key` / `--api-key-file` | API key |

### `alignment` — Run alignment auditing

```
community-ai-audit alignment <model> --provider <provider> [options]
```

| Option | Description |
|--------|-------------|
| `--scanners` / `-s` | Scanner names to run (default: all) |
| `--output` / `-o` | json (default), table |
| `--save PATH` | Save results to file |
| `--api-key` / `--api-key-file` | API key |

### `audit-score` — Compute unified score

```
community-ai-audit audit-score [options]
```

| Option | Description |
|--------|-------------|
| `--scan PATH` | Security scan results JSON |
| `--policy PATH` | Policy/compliance results JSON |
| `--reliability PATH` | Reliability results JSON |
| `--agent PATH` | Agent risk results JSON |
| `--redteam PATH` | Red team results JSON |
| `--alignment PATH` | Alignment results JSON |
| `--mechinterp PATH` | Mechanistic interpretability results JSON |
| `--weights DIM VAL` | Weight override (repeatable), e.g. `--weights alignment 0.3 --weights red_team 0.2` |
| `--output` / `-o` | json (default), table |

### `discover` — List capabilities

```
community-ai-audit discover [--format json|table]
```

### `schedule` — Cron schedules

```
community-ai-audit schedule add <name> <model> --cron <expr> [options]
community-ai-audit schedule list
community-ai-audit schedule remove <name>
community-ai-audit schedule run [--name <name>]
```

| Option | Description |
|--------|-------------|
| `--cron` | 5-field cron expression, e.g. `0 6 * * *` |
| `--provider` / `-p` | Model provider |
| `--scanners` / `-s` | Scanners to run |
| `--interpreters` / `-i` | Interpreters to run |
| `--connectors` / `-c` | Connectors to push to |
| `--profile` | quick, standard, deep, custom |
| `--output` | Report format |
| `--save-dir` | Report output directory |

Schedule sub-commands `add`/`remove`/`run` also accept `--user` and `--api-key-rbac` for RBAC.

---

## Configuration

### File: `config/default.yaml`

```yaml
cache:
  enabled: true
  max_size: 1000
  ttl_seconds: 3600

scanners:
  adversarial:
    num_samples: 32
    pgd_steps: 10
    epsilon: 0.1
  backdoor:
    sample_size: 128
    max_layers: 16
  prompt_injection:
    patterns_path: null
  data_extraction:
    max_length: 512
  toxicity:
    threshold: 0.5

interpreters:
  integrated-gradients:
    steps: 50
  lime:
    num_samples: 1000

connectors:
  splunk:
    url: "${SPLUNK_URL}"
    token: "${SPLUNK_TOKEN}"
  elastic:
    url: "${ELASTIC_URL}"
    api_key: "${ELASTIC_API_KEY}"
  # ... additional connector configs
```

### Precedence (lowest → highest)

1. `config/default.yaml` (shipped with package)
2. User config file (`--config PATH`)
3. Environment variables: `COMMUNITY_AI_AUDIT_{SECTION}_{KEY}`
4. CLI arguments

### API Key Precedence (lowest → highest)

1. `--api-key` (warns: visible in process list)
2. `--api-key-file` (reads from file, safer)
3. `COMMUNITY_AI_AUDIT_API_KEY` env var (recommended)

---

## Profiles

Profiles control scanner/interpreter selection and intensity:

| Profile | Scanners | Interpreters | Adversarial samples | Backdoor samples | IG steps | LIME samples |
|---------|----------|-------------|--------------------|-----------------|----------|-------------|
| `quick` | adversarial | integrated-gradients | 16 | 64 | — | — |
| `standard` | adversarial, backdoor | integrated-gradients | 32 | 128 | 50 | — |
| `deep` | adversarial, backdoor | integrated-gradients, lime | 128 | 512 | 100 | 2000 |
| `custom` | as specified | as specified | per override | per override | per override | per override |

---

## YAML DSL Scanner

Define custom scanners without writing Python. Example `my_rules.yaml`:

```yaml
scanner:
  name: "my-custom-scanner"
  description: "Custom rules for my domain"
  rules:
    - name: "rule-1"
      description: "Detect pattern X"
      severity: "high"
      pattern: "sensitive_pattern"
      match_type: "regex"
    - name: "rule-2"
      description: "Detect threshold Y"
      severity: "medium"
      threshold: 0.8
      metric: "entropy"
```

Loaded via the `--probe-file` or inline probe config mechanism.

---

## RBAC

Opt-in role-based access control.

### Config file: `~/.community-ai-audit/rbac.json`

```json
{
  "users": {
    "alice": {
      "password_hash": "...",
      "roles": ["admin", "auditor"]
    },
    "bob": {
      "password_hash": "...",
      "roles": ["viewer"]
    }
  },
  "roles": {
    "admin": ["admin:manage", "audit:run", "schedule:manage", "report:view"],
    "auditor": ["audit:run", "report:view"],
    "viewer": ["report:view"]
  },
  "permissions": {
    "admin:manage": "Manage users and roles",
    "audit:run": "Run audit scans",
    "schedule:manage": "Create/remove schedules",
    "report:view": "View audit reports"
  }
}
```

Usage:

```bash
community-ai-audit audit <model> -p openai --user alice --api-key-rbac <key>
```

If `--user` is not provided, RBAC is a no-op.

---

## Deployment

### Docker

```bash
docker build -t community-ai-audit .
docker run -v $(pwd)/config:/app/config community-ai-audit scan model.pt -p local
```

### Docker Compose

```bash
docker-compose up -d
# Runs the scheduler, exposes API, mounts config volumes
```

### Helm (Kubernetes)

```bash
helm install community-ai-audit ./charts/community-ai-audit
```

### Air-Gapped

```bash
# On a connected machine:
./scripts/airgap-bundle.sh

# On the air-gapped machine:
./scripts/offline-install.sh
```

---

## Testing

```bash
# Run all tests (no torch/croniter needed)
pytest tests/

# With coverage
pytest --cov=community_ai_audit tests/

# Specific test file
pytest tests/test_scheduler.py -v
```

Test scope: 477+ tests covering unit, integration, CLI smoke, connector mock, red team, mechanistic interpretability, alignment auditing, and unified scoring tests.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `COMMUNITY_AI_AUDIT_CONFIG` | Path to YAML config override |
| `COMMUNITY_AI_AUDIT_PLUGIN_PATH` | Colon-separated extra plugin directories |
| `COMMUNITY_AI_AUDIT_LOG_LEVEL` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `COMMUNITY_AI_AUDIT_API_KEY` | API key for model providers (recommended) |
| `COMMUNITY_AI_AUDIT_*` | Any config key overridable via env (e.g. `COMMUNITY_AI_AUDIT_SPLUNK_URL`) |
