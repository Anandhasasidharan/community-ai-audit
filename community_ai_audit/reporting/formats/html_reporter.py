"""HTML report format."""

from typing import Any
import json as _json


class HTMLReporter:
    """HTML report format plugin."""

    @classmethod
    def render(cls, session: Any) -> str:
        from community_ai_audit.reporting.generator import ReportGenerator

        gen = ReportGenerator()
        risk = gen._session_risk(session)
        risk_level = gen._risk_level(risk)

        findings_html = []
        for result in session.scan_results:
            for f in result.findings:
                severity = str(f.severity.value).lower()
                tag = cls._severity_tag(severity)
                findings_html.append(
                    f'<div class="finding {severity}">'
                    f'<div class="finding-header">{tag} '
                    f'<span class="finding-title">{cls._escape(f.title)}</span></div>'
                    f'<div class="finding-body">'
                    f"<p><strong>Scanner:</strong> {result.scanner_name} (v{result.scanner_version})</p>"
                    f"<p><strong>Description:</strong> {cls._escape(f.description)}</p>"
                    f'<p><strong>Severity:</strong> <span class="severity-{severity}">{severity}</span></p>'
                    f"<p><strong>Confidence:</strong> {f.confidence:.2f}</p>"
                    f'{f"<p><strong>Recommendation:</strong> {cls._escape(f.recommendation)}</p>" if f.recommendation else ""}'
                    f'{f"<details><summary>Evidence</summary><pre>{_json.dumps(f.evidence, indent=2)}</pre></details>" if f.evidence else ""}'
                    f"</div></div>"
                )

        findings_section = (
            "\n".join(findings_html) if findings_html else "<p>No findings detected.</p>"
        )

        return (
            "<!DOCTYPE html>\n"
            '<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>AI Security Audit — {cls._escape(str(session.model_id or "unknown"))}</title>'
            "<style>"
            "body{font-family:system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;background:#f8f9fa;color:#333}"
            ".header{background:#2c3e50;color:#fff;padding:20px;border-radius:8px;margin-bottom:20px}"
            ".risk-score{font-size:2em;font-weight:bold}"
            ".finding{margin:15px 0;padding:15px;border-radius:6px;box-shadow:0 1px 3px rgba(0,0,0,0.1)}"
            ".finding.critical{background:#f8d7da;border-left:4px solid #dc3545}"
            ".finding.high{background:#fff3cd;border-left:4px solid #ffc107}"
            ".finding.medium{background:#d1ecf1;border-left:4px solid #17a2b8}"
            ".finding.low{background:#d4edda;border-left:4px solid #28a745}"
            ".finding.info{background:#e2e3e5;border-left:4px solid #6c757d}"
            "</style></head><body>"
            f'<div class="header">'
            f"<h1>AI Security Audit Report</h1>"
            f'<p>Model: <strong>{cls._escape(str(session.model_id or "unknown"))}</strong></p>'
            f"<p>Session: {session.session_id}</p>"
            f'<p class="risk-score">Risk: {risk:.1f}/100 ({risk_level})</p>'
            f"</div>"
            f"<h2>Findings ({session.total_findings})</h2>"
            f"{findings_section}"
            "</body></html>"
        )

    @staticmethod
    def _escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    @staticmethod
    def _severity_tag(severity: str) -> str:
        tags = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
            "info": "⚪",
        }
        return tags.get(severity, "⚪")
