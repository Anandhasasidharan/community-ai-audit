# Community AI Audit — Features & Components

## CLI Commands

| Command | Description | Key Output Formats |
|---------|-------------|-------------------|
| `audit` | Full audit: load model → run scanners + interpreters → report | markdown, json, html, **modelcard** |
| `scan` | Run vulnerability scanners only | markdown, json, html |
| `interpret` | Run interpretability methods only | markdown, json, html |
| `eval` | Full evaluation: scan + policy + reliability + scoring | json, markdown |
| `benchmark` | Run model against a benchmark dataset | json, table |
| `regression` | Compare two benchmark runs for regression | json, table |
| `redteam` | Red team security testing (jailbreak, roleplay, obfuscation, multi-turn, exploitation) | json, table |
| `mechinterp` | Mechanistic interpretability analysis (activations, attention, features, layers, representations) | json, table |
| `alignment` | Alignment evaluation (sycophancy, value alignment, preference drift, objective robustness) | json, table |
| `audit-score` | Compute unified audit score from all result dimensions | json, table |
| `agent-audit` | Agent audit scanners on a session file | json, table |
| `agent-trace` | Manage/export agent execution traces | json, jsonl, html, markdown |
| `agent-dashboard` | Generate agent monitoring HTML dashboard | html, json |
| `agent-monitor` | Agent monitoring: audit, history, alerts, drift | json, table |
| `schedule` | Recurring audit schedules (add, list, remove, run) | — |
| `discover` | List all plugins, adapters, and connectors | json, table |
| `datasets` | List available benchmark datasets | json, table |

---

## Scanner Plugins (7)

| Scanner | Type | What It Detects |
|---------|------|-----------------|
| **adversarial** | White-box | FGSM + PGD attack success rate, robustness score |
| **backdoor** | White-box | Trojan/backdoor via activation clustering, anomalous layer patterns |
| **prompt_injection** | Black-box | DAN, system prompt extraction, 10+ injection techniques |
| **toxicity** | Black-box | Toxic/bias/harmful content generation, 12 probe categories |
| **data_extraction** | Black-box | Training data memorization, 20+ extraction probes |
| **watermark** | White-box | Suspicious weight patterns: extreme sparsity, low variance |
| **dsl_scanner** | Both | YAML-defined custom scanners without writing Python |

---

## Interpreter Plugins (2)

| Interpreter | Type | Method |
|-------------|------|--------|
| **integrated-gradients** | White-box | Path-integrated gradients, configurable steps/baseline |
| **lime** | Black-box | Perturbation-based local explanations, sparse linear model |

---

## Alignment Plugins (4)

| Scanner | Description |
|---------|-------------|
| **sycophancy** | Tests if model agrees with user's opinion vs. independent judgment |
| **value_alignment** | Ethical dilemma prompts: honesty, legality, beneficence, fairness |
| **preference_drift** | Detects inconsistent preferences across paraphrased questions |
| **objective_robustness** | Tests goal consistency across helpful/harmless/accuracy/privacy domains |

---

## Red Team Plugins (5)

| Scanner | Description |
|---------|-------------|
| **jailbreak** | 20 jailbreak prompts: DAN, roleplay as rogue AI, hypothetical scenarios |
| **roleplay** | 15 roleplay bypasses: journalist, teacher, movie character, etc. |
| **obfuscation** | Base64, leet speak, ROT13, reversed text — 10 encoded probes |
| **multi_turn** | 10 two-turn conversational attack progressions |
| **exploitation** | Tool exploitation: webshell, SQL injection, credential dumping — 10 probes |

---

## Mechinterp Analyzers (5)

| Analyzer | Description |
|----------|-------------|
| **activation_probes** | Probes model activations across 5+ probe inputs |
| **attention_head** | Estimates attention patterns and head specialization |
| **feature_attribution** | Identifies which input features drive outputs |
| **layer_analysis** | Analyzes behavior across early/mid/late layers |
| **representation** | Measures latent representation distances across concept pairs |

---

## Agent Scanners (5)

| Scanner | Description |
|---------|-------------|
| **ToolAbuseScanner** | Detects excessive or dangerous tool invocation patterns |
| **MemoryPoisoningScanner** | Flags attempts to corrupt agent memory/context |
| **GoalDriftScanner** | Detects divergence from original task objective |
| **PermissionEscalationScanner** | Identifies unauthorized privilege escalation attempts |
| **UnsafeActionScanner** | Flags destructive or unsafe agent actions |

---

## Reporting Formats

| Format | Commands | Description |
|--------|----------|-------------|
| **markdown** | audit, scan, interpret | Readable Markdown report |
| **json** | All commands | Structured JSON for pipelines |
| **html** | audit, scan, interpret | Standalone styled HTML page |
| **modelcard** | audit | Mitchell et al. (2019) model card with YAML front matter |
| **table** | benchmark, regression, discover, etc. | CLI table output |
| **dashboard** | audit (via plugin) | Dashboard-style rich HTML |

---

## Connectors (13)

### SIEM
| Connector | Target |
|-----------|--------|
| splunk | Splunk HEC |
| elastic | Elasticsearch bulk API |
| sentinel | Microsoft Sentinel |
| datadog | Datadog Logs API |
| qradar | IBM QRadar REST API |
| logrhythm | LogRhythm REST API |
| sumologic | Sumo Logic HTTP Source |
| webhook | Generic HTTP/S webhook |

### Vector DB (findings as vectors)
| Connector | Target |
|-----------|--------|
| pinecone | Pinecone vector DB |
| weaviate | Weaviate vector DB |

### Cloud Storage
| Connector | Target |
|-----------|--------|
| s3 | AWS S3 |
| gcs | Google Cloud Storage |
| azure_blob | Azure Blob Storage |

---

## Model Providers (9)

| Provider | Adapter | Model Types |
|----------|---------|-------------|
| huggingface | huggingface | Text, Image, Multimodal, Embedding |
| openai | openai | GPT-4/3.5 (Chat Completions) |
| anthropic | anthropic | Claude API |
| aws_bedrock | aws_bedrock | Claude, Llama, Mistral, Titan, Cohere |
| local | local | .pt, .pth, .safetensors, .onnx, HF directories |
| ollama | ollama | Local Ollama models |
| groq | groq | Groq fast inference |
| replicate | replicate | Replicate cloud platform |
| vertexai | vertexai | Google Vertex AI (Gemini) |

---

## Core Components

| Component | File | Responsibility |
|-----------|------|----------------|
| **AuditEngine** | `core/audit.py` | Model loading, scanner/interpret execution, session management, connector dispatch |
| **Plugin Registry** | `core/registry.py` | Discovers plugins from built-in modules, entry points, config paths, env vars |
| **ScoringEngine** | `core/scoring/engine.py` | 7-dimension weighted risk score (security, reliability, compliance, agent_risk, alignment, red_team, interpretability) |
| **EvaluationEngine** | `core/evaluation/engine.py` | Orchestrates evaluate(), benchmark(), regression() |
| **AuditScheduler** | `core/scheduler.py` | Cron-based recurring audit scheduling |
| **AccessControl (RBAC)** | `core/rbac.py` | Role-based access: admin, auditor, viewer — per-user API key auth |
| **AgentAuditSession** | `core/agent_session.py` | TraceStep model with 6 action types, JSON import/export, replay |
| **Tracing** | `core/tracing/` | Export and replay for agent execution traces |
| **AuditDiff** | `diff.py` | Compares two audit sessions: new/resolved/changed findings, severity shifts |
| **ReportGenerator** | `reporting/generator.py` | Renders sessions to markdown, json, html, modelcard |
| **AlertManager** | `monitoring/alerts.py` | Info/warning/critical alerting, persisted to JSONL |
| **DriftDetector** | `monitoring/drift.py` | Baseline comparison for score drift |
| **TrendAnalyzer** | `monitoring/trends.py` | Time-series trend analysis |

---

## Policy & Reliability Plugins

### Policies (3)
| Plugin | Description |
|--------|-------------|
| NoPiiLeakagePolicy | Detects PII leakage in model outputs |
| NoMalwareGenerationPolicy | Detects malicious code generation |
| NoSystemPromptDisclosurePolicy | Detects prompt extraction attempts |

### Reliability Scanners (4)
| Scanner | Description |
|---------|-------------|
| HallucinationScanner | Measures factual consistency |
| ConsistencyScanner | Tests response consistency across rephrased queries |
| CalibrationScanner | Evaluates confidence calibration |
| CitationScanner | Verifies citation accuracy |

---

## Configuration

| Source | Format | What It Controls |
|--------|--------|-----------------|
| Default config | `config/default.yaml` | Cache dir, device, dtype, scanner defaults, profile presets |
| User config | YAML via `--config` / env var | Deep-merged overrides |
| Connector configs | `config/connectors/*.yaml` | Per-connector auth, endpoints, settings |
| Environment | `COMMUNITY_AI_AUDIT_*` vars | API keys, config path, log level, plugin paths |
| RBAC config | `~/.community-ai-audit/rbac.yaml` | Users, roles, permissions |
| Profiles | `--profile quick\|standard\|deep\|custom` | Scanner/interpreter selection + intensity tuning |

---

## Security Framework References

Findings can carry references to all major AI security frameworks:
- **CWE** — Common Weakness Enumeration (e.g. CWE-20)
- **MITRE ATLAS / ATT&CK** — Adversarial Threat Landscape (e.g. AI-A1002)
- **NIST AI RMF** — AI Risk Management Framework categories

---

## Demo App

FastAPI web app in `demo_app/`:
- `POST /api/audit` — triggers audit on DistilGPT2
- `GET /api/status/{id}` — poll audit status
- `GET /api/results/{id}` — fetch results
- `GET /` — Chart.js dashboard: Overview, Scanners, Interpreters, Agent Audit, Red Team, History tabs

---

## Tests — 570 tests across 31 files

| Area | Files |
|------|-------|
| Core | test_core, test_registry, test_rbac, test_scheduler, test_retry, test_cli, test_cli_ui, test_smoke |
| Audit Engine | test_audit_engine |
| Scanners | test_scanners, test_scanners_v040 |
| Interpreters | test_interpreters |
| Policies | test_policies |
| Reliability | test_reliability |
| Red Team | test_redteam, test_persistence |
| Alignment | test_alignment |
| Mechinterp | test_mechinterp |
| Agents | test_agent_scanners |
| Connectors | test_connectors_smoke |
| Reporting | test_report_generator |
| Evaluation | test_evaluation_engine, test_models, test_trends |
| Scoring | test_scoring_engine |
| Datasets | test_datasets |
| Benchmarks | test_benchmarks |
| Monitoring | test_monitoring |
| Tracing | test_tracing |
| Integration | integration_check |

---

## What Makes This Unique

Unlike any other tool, `community-ai-audit` runs **live security scans** against a model (adversarial robustness, backdoor detection, prompt injection, toxicity, data extraction, watermark analysis, jailbreak testing, alignment evaluation, etc.) and outputs a **complete model card** populated with actual findings, severity metrics, CWE/MITRE/NIST references, and recommendations — all from a single CLI command.

No separate documentation step. No manual entry. The model card is a byproduct of the audit.
