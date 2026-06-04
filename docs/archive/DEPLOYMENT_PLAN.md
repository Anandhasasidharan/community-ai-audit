# Community AI Security Audit Tool — GitHub Deployment Plan

> **Current date:** 2026-05-30  
> **Current state:** Core architecture scaffolded; stabilization & hardening needed  
> **Target:** Public GitHub repo with installable `pip` package + working CLI

---

## Phase 0: Hardening Sprint (Week 1) — *Current priority*

**Goal:** Every module imports cleanly. Discovery works. CLI doesn't crash.

| Task | Status | Owner |
|------|--------|-------|
| Fix registry discovery for adapters/connectors (SIEMs showing empty) | 🔴 Open | dev |
| Fix remaining import/syntax issues (orphan `import os`, etc.) | 🟡 In progress | dev |
| Clean up `_register_from_module` to exclude abstract classes | 🟡 In progress | dev |
| Audit all `__init__.py` re-exports to avoid circular imports | 🔴 Open | dev |
| Make `community-ai-audit discover` list all built-ins correctly | 🔴 Open | dev |

**Deliverable:** `python -m community_ai_audit.cli.main discover` shows all adapters, connectors, scanners, and interpreters.

---

## Phase 1: Core E2E Working (Week 2)

**Goal:** A user can install and run a real audit end-to-end.

| Task | Notes |
|------|-------|
| Implement `load_model` for at least **3 adapters**: HuggingFace, OpenAI, Local | Local adapter is closest to done |
| Implement **1 working scanner** (backdoor or adversarial) with real logic | Currently placeholder stubs |
| Implement **1 working interpreter** (integrated gradients or LIME) | Currently placeholder stubs |
| Wire `AuditEngine.audit()` full pipeline: load → scan → interpret → report | Depends on above |
| Test CLI: `community-ai-audit scan <model> --provider local` | |

**Deliverable:** A working `scan` command that produces a Markdown report with real findings.

---

## Phase 2: Connector Integration (Week 3)

**Goal:** Push audit results to at least 2 SIEMs.

| Task | Notes |
|------|-------|
| Fix and test **Splunk HEC** connector | Logic is there; needs live test |
| Fix and test **Elastic** connector | Logic is there; needs live test |
| Add connector config examples in `config/` | |
| Add `--connector splunk --connector elastic` CLI flags | Shell exists; wire through |
| Validate event schema works in real Splunk/Elastic instances | Requires test instances |

**Deliverable:** `community-ai-audit audit <model> --connectors splunk elastic` pushes events successfully.

---

## Phase 3: Documentation & Onboarding (Week 4)

**Goal:** A stranger can clone, install, and run the tool.

| Task | Notes |
|------|-------|
| Write `README.md` with quickstart, architecture diagram, and provider matrix | |
| Document how to add a **new adapter** (step-by-step) | Target: 30 min for a contributor |
| Document how to add a **new SIEM connector** | Target: 30 min for a contributor |
| Document how to add a **new scanner** or **interpreter** | Target: 30 min for a contributor |
| Add `docs/` folder with `ARCHITECTURE.md`, `CONTRIBUTING.md`, `PLUGIN_GUIDE.md` | |
| Create example configs for each provider in `examples/` | HuggingFace, OpenAI, local, etc. |

**Deliverable:** A contributor can add a new adapter/connector/scanner by reading the guide.

---

## Phase 4: Tests & CI (Week 5)

**Goal:** Green CI. No regressions.

| Task | Notes |
|------|-------|
| Write unit tests for `Registry` discovery | Mock modules for isolation |
| Write unit tests for `AuditEngine` orchestration | Mock adapters/connectors |
| Write unit tests for at least 1 adapter (local/HuggingFace) | Use tiny test models |
| Write unit tests for at least 1 scanner | Use synthetic data |
| Set up **GitHub Actions**: lint (ruff/black), type-check, test | |
| Set up **GitHub Actions**: build package, check install | |

**Deliverable:** PRs blocked on failing CI. `pytest` passes locally and in CI.

---

## Phase 5: GitHub Repo Launch (Week 6)

**Goal:** Public repo, installable via pip, first release tagged.

| Task | Notes |
|------|-------|
| Create `community-ai-audit` repo on GitHub | Pick org or personal |
| Push code to `main`, tag `v0.1.0` | |
| Publish to **PyPI** (`pip install community-ai-audit`) | `pyproject.toml` already set up |
| Create **release notes** with feature list and known limitations | |
| Post on relevant communities (AI safety, infosec, ML) | |

**Deliverable:** `pip install community-ai-audit` works on a clean environment.

---

## Phase 6: Community & Iteration (Post-launch)

| Milestone | Target |
|-----------|--------|
| Community contributes first external adapter | Month 2 |
| Community contributes first external scanner | Month 2–3 |
| Add 2 more SIEM connectors (Chronicle, Graylog, etc.) | Month 2–3 |
| Add SOAR integration (e.g. Palo Alto XSOAR, Splunk SOAR) | Month 3 |
| Add signature sharing / community database | Month 3–4 |
| v0.2.0 milestone | Month 3 |

---

## Summary Timeline

| Phase | Dates (2026) | What’s ready |
|-------|--------------|-------------|
| 0. Hardening | May 30 – Jun 6 | Clean imports, discovery works |
| 1. Core E2E | Jun 7 – Jun 13 | `scan` command produces real report |
| 2. Connectors | Jun 14 – Jun 20 | SIEM push working |
| 3. Docs | Jun 14 – Jun 20 (parallel) | Contributor can add plugins |
| 4. Tests & CI | Jun 21 – Jun 27 | Green CI, pytest passes |
| 5. **GitHub Launch** | **Jun 28 – Jul 4** | **Public repo, pip installable** |
| 6. Community | Ongoing | Contributions, v0.2.0 |

---

## Immediate next step (today)

Finish Phase 0 — hardening. I can do this now if you’d like:

1. Fix all registry discovery issues (connectors showing empty)
2. Clean all imports & syntax
3. Make `discover` output complete and correct
4. Verify `python -m community_ai_audit.cli.main` works end-to-end without crashes

**Do you want me to finish the hardening pass right now?**
