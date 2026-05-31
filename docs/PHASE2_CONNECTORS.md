# Phase 2: SIEM / Connector Integration Guide

This phase focuses on productionizing connector integrations for:
- Splunk (HEC)
- Elastic Security
- Datadog
- Microsoft Sentinel

---

## Objectives

1. Ensure event schema consistency across connectors.
2. Add retry/error handling and clear failure diagnostics.
3. Add connector-level tests with mocked network calls.
4. Provide reproducible local verification commands.

---

## Event Schema Contract (recommended)

Each connector should receive normalized events with at least:

- `event_type` (scan_result / interpretation_result)
- `title`
- `description`
- `severity`
- `confidence`
- `model_id`
- `scanner_name` or `interpreter_name`
- `timestamp`

Optional enrichment fields:
- `cwe_id`
- `mitre_id`
- `recommendation`
- `evidence`

---

## Environment Setup

Use `.env.example` and set platform credentials:

- Splunk: `SPLUNK_HEC_URL`, `SPLUNK_HEC_TOKEN`
- Elastic: `ELASTICSEARCH_URL` (+ auth)
- Datadog: `DD_SITE`, `DD_API_KEY`, `DD_APP_KEY`
- Sentinel: `AZURE_LOG_ANALYTICS_WORKSPACE_ID`, `AZURE_LOG_ANALYTICS_KEY`

---

## Validation Flow

1. Run unit/smoke tests:

```bash
python -m unittest discover -s tests -v
```

2. Run a local audit and push to one connector:

```bash
community-ai-audit audit artifacts/toy_model.pt \
  --provider local \
  --profile standard \
  --scanners adversarial backdoor \
  --interpreters integrated-gradients \
  --probe-file examples/data/toy_probe.json \
  --input '[0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1]' \
  --connectors splunk
```

3. Verify event ingestion in target SIEM.

---

## Hardening checklist

- [ ] Connector retries with bounded backoff
- [ ] Request timeout policy documented
- [ ] Connector-specific schema mapping tests
- [ ] Explicit auth failure messages
- [ ] Batch chunking limits per platform
- [ ] Dead-letter or fallback logging path

---

## Notes

Current implementation is suitable for pre-release validation. For production,
add secret management (vault), stronger retry control, and integration tests
against real sandbox tenants.