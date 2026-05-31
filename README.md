# Community AI Security Audit Tool

A community-driven tool for auditing AI models for security vulnerabilities using interpretability techniques. Built for cybersecurity researchers, ML engineers, and AI safety enthusiasts.

## Features

- **Vulnerability Scanning** — Detect backdoors, adversarial vulnerabilities, data poisoning, model stealing risks, and membership inference.
- **Interpretability Analysis** — Apply integrated gradients, LIME, activation clustering, and more to explain model behavior.
- **Risk Scoring & Reporting** — Generate actionable reports (Markdown, JSON, HTML) with severity scores and mitigation suggestions.
- **Community Sharing** — Share audit results, signatures, and detection rules via a lightweight database or git-based sharing.

## Installation

```bash
pip install community-ai-audit
```

*(Not yet published — install from source for now)*

```bash
git clone https://github.com/your-org/community-ai-audit.git
cd community-ai-audit
pip install -e .
```

## Quick Start

```bash
# Discover built-in adapters/connectors/plugins
community-ai-audit discover

# Scan a local model
community-ai-audit scan my_model.pt --provider local --scanners adversarial --probe-file examples/data/toy_probe.json

# Full audit
community-ai-audit audit my_model.pt --provider local --profile standard --scanners adversarial backdoor --interpreters integrated-gradients --probe-file examples/data/toy_probe.json --input '[0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1]'

# Interpret model predictions
community-ai-audit interpret my_model.pt --provider local --interpreters integrated-gradients --input '[0.2,0.1,0.0,0.3]'
```

## Phase 1 demo (toy model)

```bash
# Create a reproducible toy model artifact
python3 examples/create_toy_model.py --out artifacts/toy_model.pt --in-features 16 --classes 3

# Run API-based toy demo
python3 examples/phase1_toy_demo.py
```

For full CLI benchmark commands, see: `docs/PHASE1_BENCHMARK.md`

To save reproducible benchmark artifacts (markdown + JSON):

```bash
python3 examples/run_phase1_benchmark.py --model artifacts/toy_model.pt --probe-file examples/data/toy_probe.json --profile standard --out-dir reports/phase1
```

## Supported Frameworks

- PyTorch
- TensorFlow
- HuggingFace Transformers

## Project Status

🚧 **Pre-release (v0.1.0)** — Core infrastructure in progress.

## Contributing

We welcome contributions! See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

## License

MIT License — see [LICENSE](LICENSE).