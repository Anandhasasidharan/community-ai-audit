# Architecture

## Overview
Community AI Security Audit Tool is built around a plug-and-play plugin architecture.

### Core layers
- **Model Adapters**: connect to any provider (HuggingFace, OpenAI, Anthropic, Bedrock, local, Ollama)
- **Connectors**: push findings into SIEM/security tools (Splunk, Elastic, Datadog, Sentinel)
- **Plugins**: scanners, interpreters, reporters
- **Audit Engine**: orchestrates load → scan → interpret → report → export

### Discovery
Plugins are discovered through:
1. built-in package scanning
2. Python entry points
3. user-provided plugin paths

### Guiding principle
Anything that implements the interface should work without changing the core.