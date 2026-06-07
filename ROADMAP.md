# Roadmap

## v0.1.0 — Foundation (Current)

- [x] Plug-and-play model adapters (OpenAI, Anthropic, HuggingFace, AWS Bedrock, Local, Ollama)
- [x] SIEM connectors (Splunk, Elastic, Datadog, Sentinel)
- [x] Built-in scanners (backdoor detection, adversarial robustness)
- [x] Built-in interpreters (integrated gradients, LIME)
- [x] CLI with `discover`, `scan`, `interpret`, `audit` commands
- [x] Markdown, JSON, HTML reporting (markdown, json in ReportGenerator; HTML reporter plugin)
- [x] CI/CD pipeline with lint, test, publish
- [x] Contributor guides (adapter, scanner, connector, interpreter)

## v0.2.0 — Analysis & Performance

- [x] Performance benchmarks with latency/throughput tracking
- [x] Caching layer for repeated model queries
- [x] Batch scan mode for large model evaluations
- [x] Parallel connector dispatch
- [x] Configurable severity thresholds per scanner
- [x] Audit summary diff (compare two audit runs)
- [x] Dashboard export (HTML + embedded charts)

## v0.3.0 — Extended Integrations

- [x] Additional model providers: Google Vertex AI, Groq, Replicate
- [x] Additional SIEM connectors: QRadar, LogRhythm, Sumo Logic
- [x] Vector database connectors (Pinecone, Weaviate)
- [x] Cloud storage connectors (S3, GCS, Azure Blob)
- [x] Webhook connector for custom integrations

## v0.4.0 — Advanced Scanners (Current)

- [x] Prompt injection scanner
- [x] Data extraction / memorization scanner
- [x] Toxicity / bias scanner
- [x] Model watermark detection
- [x] Custom scanner DSL

## v0.5.0 — Production Readiness (Current)

- [x] Helm chart for Kubernetes deployment
- [x] Docker compose for local evaluation
- [x] Air-gapped installation support
- [x] Audit scheduling (cron-based recurring audits)
- [x] Role-based access for multi-user deployments

## Known Limitations

- Adapters require the model provider's SDK installed
- SIEM connectors require live credentials (no mock mode for testing)
- Scanners currently work with PyTorch models only (TensorFlow planned)
- Interpreters require access to model internals (gradients, activations)
- Large model audits can be slow — batch mode will help
