# Model Card Generation: Competitive Landscape

## Products & Tools

| Product | Type | Input Source | Output Format | Open Source | Model Card from Security Scans? |
|---------|------|-------------|---------------|-------------|-------------------------------|
| **community-ai-audit** | CLI tool | Live security scan results (adversarial, backdoor, toxicity, prompt injection, etc.) | Mitchell et al. model card (Markdown) | Yes (MIT) | **Yes — core feature** |
| **NVIDIA MCG Toolkit** (May 2026) | CLI tool + LLM pipeline | Static source code, config files, repo structure | Model Card++ (overview + 4 subcards: Bias, Explainability, Privacy, Safety & Security) | No (proprietary) | No — generates from code, not from running security probes |
| **FRAI** (frai.cc) | CLI + SDK (JS/TS) | Code scanning, file analysis | Model card, risk files, eval reports | Yes (MIT) | No — scans code structure, not model behavior |
| **OWASP AIBOM Generator** | Python library | Manual metadata, dependency scan | CycloneDX ML-BOM (JSON/XML) | Yes (Apache 2.0) | No — AI supply chain SBOM, not security findings |
| **Protect AI ModelScan** | CLI tool (Python) | Serialized model files (Pickle, H5, SavedModel) | Security report | Yes (Apache 2.0) | No — detects serialization malware only |
| **Red Hat AI System Cards** | Schema/GitHub spec | Manual entry | Markdown schema | Yes (CC BY 4.0) | No — conceptual framework, no generation tooling |
| **MEOK AI BOM MCP** | MCP server (Python) | User-provided metadata | CycloneDX ML-BOM (JSON) | Yes (MIT) | No — AI-BOM format, manual metadata entry |
| **WatchDog Security** | SaaS platform | Manual entry + integrations | Compliance document | No | No — enterprise governance portal |
| **Securiti AI** | SaaS platform | Manual entry + integrations | Governance document | No | No — enterprise governance portal |

## Core Differentiator

**community-ai-audit** is the only tool that generates model cards directly from **live, running security scans** against the model. Every other tool either:

- Extracts metadata from **static source code** (NVIDIA MCG, FRAI)
- Documents **supply chain dependencies** (OWASP AIBOM, MEOK)
- Provides **templates for manual entry** (WatchDog, Securiti, Red Hat)
- Scans **file format vulnerabilities only** (Protect AI ModelScan)

## How It Works

```
community-ai-audit audit my-model --provider huggingface --output modelcard
```

This single command:
1. Loads the model into memory
2. Runs adversarial probes (FGSM, PGD) → populates **Quantitative Analyses**
3. Runs toxicity/bias scans → populates **Ethical Considerations**
4. Runs backdoor, prompt injection, data extraction scanners → populates **Evaluation Data**
5. Maps findings to CWE/MITRE/NIST references → populates **Security References**
6. Extracts severity counts → populates **Metrics** table
7. Outputs a complete Mitchell et al. model card with all sections filled

No other tool chains actual security testing into model card generation. The model card is a **byproduct of audit**, not a separate documentation step.
