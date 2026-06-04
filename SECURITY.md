# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | ✅ Active development |

## Reporting a Vulnerability

This is a security audit tool designed to identify vulnerabilities in AI models.
If you discover a security issue **in the tool itself**, please report it privately.

**Do not** file a public GitHub issue for security vulnerabilities.

### How to Report

1. **Email**: Open a [GitHub Security Advisory](https://github.com/Anandhasasidharan/community-ai-audit/security/advisories)
2. **Response time**: Within 48 hours
3. **Process**: We'll acknowledge, investigate, and release a fix

## Scope

The following are **in scope** for security reports:

- Code execution vulnerabilities in the audit engine
- Data leakage between model adapters and the host
- Authentication bypass in SIEM connectors
- Insecure deserialization in plugin loading

The following are **out of scope** (by design):

- Vulnerabilities discovered in the *models being audited* (that's the tool's purpose)
- Known limitations documented in `docs/PHASE1_BENCHMARK.md`

## Safe Use

- Always run audits in isolated environments when testing untrusted models
- Connectors require API credentials — store them in environment variables, not in code
- See `.env.example` for required environment variable names
