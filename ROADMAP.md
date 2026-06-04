# Roadmap

## v0.1.0 — Foundation (Current)

- [x] Plug-and-play model adapters (OpenAI, Anthropic, HuggingFace, AWS Bedrock, Local, Ollama)
- [x] SIEM connectors (Splunk, Elastic, Datadog, Sentinel)
- [x] Built-in scanners (backdoor detection, adversarial robustness)
- [x] Built-in interpreters (integrated gradients, LIME)
- [x] CLI with `discover`, `scan`, `interpret`, `audit` commands
- [x] Markdown, JSON, HTML reporting
- [x] CI/CD pipeline with lint, test, publish
- [x] Contributor guides (adapter, scanner, connector, interpreter)

## v0.2.0 — Analysis & Performance

- [ ] Performance benchmarks with latency/throughput tracking
- [ ] Caching layer for repeated model queries
- [ ] Batch scan mode for large model evaluations
- [ ] Parallel connector dispatch
- [ ] Configurable severity thresholds per scanner
- [ ] Audit summary diff (compare two audit runs)
- [ ] Dashboard export (HTML + embedded charts)

## v0.3.0 — Extended Integrations

- [ ] Additional model providers: Google Vertex AI, Groq, Replicate
- [ ] Additional SIEM connectors: QRadar, LogRhythm, Sumo Logic
- [ ] Vector database connectors (Pinecone, Weaviate)
- [ ] Cloud storage connectors (S3, GCS, Azure Blob)
- [ ] Webhook connector for custom integrations

## v0.4.0 — Advanced Scanners

- [ ] Prompt injection scanner
- [ ] Data extraction / memorization scanner
- [ ] Toxicity / bias scanner
- [ ] Model watermark detection
- [ ] Custom scanner DSL

## v0.5.0 — Production Readiness

- [ ] Helm chart for Kubernetes deployment
- [ ] Docker compose for local evaluation
- [ ] Air-gapped installation support
- [ ] Audit scheduling (cron-based recurring audits)
- [ ] Role-based access for multi-user deployments

## Known Limitations

- Adapters require the model provider's SDK installed
- SIEM connectors require live credentials (no mock mode for testing)
- Scanners currently work with PyTorch models only (TensorFlow planned)
- Interpreters require access to model internals (gradients, activations)
- Large model audits can be slow — batch mode will help
