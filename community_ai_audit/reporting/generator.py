"""
Report generator — formats ScanResult, InterpretationResult, and AuditSession
into Markdown, JSON, and HTML.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from community_ai_audit.core.audit import AuditSession

from community_ai_audit.core.interfaces import ScanResult, InterpretationResult, Severity


class ReportGenerator:
    """Generates formatted audit reports from scan and interpret results."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def render_scan_results(self, results: List["ScanResult"], fmt: str = "markdown") -> str:
        if fmt == "json":
            return json.dumps([r.to_dict() for r in results], indent=2, default=str)

        lines = []
        for result in results:
            scanner_risk = self._scanner_risk(result)
            lines.append(f"## Scanner: {result.scanner_name} (v{result.scanner_version})")
            lines.append(f"Severity: {result.overall_severity.value}")
            lines.append(f"Findings: {len(result.findings)}")
            lines.append(f"Risk score: **{scanner_risk:.1f}/100**")

            for f in result.findings:
                severity_tag = self._severity_tag(f.severity.value)
                lines.append(f"\n### {severity_tag} {f.title}")
                lines.append(f"**Description:** {f.description}")
                if f.evidence:
                    lines.append(f"**Evidence:** {f.evidence}")
                lines.append(f"**Severity:** {f.severity.value}")
                lines.append(f"**Confidence:** {f.confidence:.2f}")
                lines.append(f"**Recommendation:** {f.recommendation or '(none)'}")
            lines.append("\n---\n")

        return "\n".join(lines)

    def render_interpret_results(
        self, results: List["InterpretationResult"], fmt: str = "markdown"
    ) -> str:
        if fmt == "json":
            return json.dumps([r.to_dict() for r in results], indent=2, default=str)

        lines = []
        for result in results:
            lines.append(
                f"## Interpreter: {result.interpreter_name} (v{result.interpreter_version})"
            )
            if result.error:
                lines.append(f"**Error:** {result.error}")
            else:
                lines.append(f"**Summary:** {result.summary}")
                if result.attributions:
                    lines.append(
                        f"**Attributions (top):** {self._truncate_text(str(result.attributions), 1200)}"
                    )
            lines.append("\n---\n")

        return "\n".join(lines)

    def render_session(self, session: "AuditSession", fmt: str = "markdown") -> str:
        if fmt == "dashboard":
            from community_ai_audit.plugins.reporters.dashboard import DashboardReporter

            risk_score = self._session_risk(session)
            risk_level = self._risk_level(risk_score)
            metadata = {
                "session_id": session.session_id,
                "model_id": session.model_id,
                "total_findings": session.total_findings,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "started_at": session.started_at.isoformat() if session.started_at else "",
                "duration_seconds": session.duration_seconds,
            }
            return DashboardReporter().render(
                session.scan_results, session.interpret_results, metadata
            )

        if fmt == "json":
            payload = session.to_dict()
            payload["risk_score"] = self._session_risk(session)
            payload["risk_level"] = self._risk_level(payload["risk_score"])
            return json.dumps(payload, indent=2, default=str)

        risk_score = self._session_risk(session)
        risk_level = self._risk_level(risk_score)

        lines = [
            "# Community AI Security Audit Report",
            "",
            f"**Session ID**: `{session.session_id}`",
            f"**Model**: {session.model_id or '(unknown)'} (adapter: {session.adapter_name or 'n/a'})",
            f"**Started**: {session.started_at.isoformat() if session.started_at else 'n/a'}",
            f"**Completed**: {session.completed_at.isoformat() if session.completed_at else 'n/a'}",
            f"**Duration**: {session.duration_seconds:.2f}s",
            "",
            f"**Total findings**: {session.total_findings}",
            f"**Highest severity**: {session.highest_severity.value if hasattr(session.highest_severity, 'value') else session.highest_severity}",
            f"**Risk score**: **{risk_score:.1f}/100** ({risk_level})",
            "",
        ]

        run_meta = getattr(session, "metadata", {}) or {}
        if run_meta:
            lines.append("## Run Metadata")
            for k, v in run_meta.items():
                lines.append(f"- **{k}**: {self._truncate_text(str(v), 300)}")
            lines.append("")

        lines.append("## Scanner Risk Summary")

        if session.scan_results:
            for r in session.scan_results:
                lines.append(
                    f"- `{r.scanner_name}`: {self._scanner_risk(r):.1f}/100 "
                    f"(severity: {r.overall_severity.value}, findings: {len(r.findings)})"
                )
        else:
            lines.append("- No scanner results.")

        lines.extend(["", "---", ""])

        if fmt == "html":
            markdown_scan = self.render_scan_results(session.scan_results, fmt="markdown")
            markdown_interp = self.render_interpret_results(
                session.interpret_results, fmt="markdown"
            )
            body = "\n".join(lines)
            return self._markdown_to_html(
                body, markdown_scan, markdown_interp, risk_score, risk_level, session
            )

        lines.append(self.render_scan_results(session.scan_results, fmt=fmt))
        lines.append(self.render_interpret_results(session.interpret_results, fmt=fmt))

        if session.connector_results:
            lines.append("\n## Connector Results")
            for name, status in session.connector_results.items():
                lines.append(f"- **{name}**: {status}")

        return "\n".join(lines)

    def render_modelcard(self, session: "AuditSession") -> str:
        risk_score = self._session_risk(session)
        risk_level = self._risk_level(risk_score)
        sev = session.highest_severity
        sev_str = sev.value if isinstance(sev, Severity) else str(sev)

        now = session.completed_at or session.started_at
        date_str = now.strftime("%Y-%m-%d") if now else "unknown"

        run_meta = getattr(session, "metadata", {}) or {}

        lines = [
            "---",
            "model-card:",
            "  version: 1.0.0",
            f"  generated: {date_str}",
            "  generator: Community AI Audit",
            f"  session: {session.session_id}",
            "---",
            "",
            f"# Model Card: {session.model_id or 'unknown'}",
            "",
            "## Model Details",
            "",
            f"- **Model**: {session.model_id or '(unknown)'}",
            f"- **Adapter**: {session.adapter_name or 'n/a'}",
            f"- **Audit Date**: {date_str}",
            f"- **Session ID**: {session.session_id}",
            f"- **Risk Score**: {risk_score:.1f}/100 ({risk_level})",
            f"- **Total Findings**: {session.total_findings}",
            f"- **Highest Severity**: {sev_str}",
            "",
        ]

        profile = run_meta.get("profile", "standard")
        provider = run_meta.get("provider", "unknown")
        lines.extend(
            [
                "## Intended Use",
                "",
                f"Audited using the **{profile}** profile via {provider}.",
                "This model card is auto-generated from security audit results.",
                "",
                "## Factors",
                "",
            ]
        )
        if run_meta:
            for k, v in run_meta.items():
                lines.append(f"- **{k}**: {self._truncate_text(str(v), 200)}")
        else:
            lines.append("- No additional metadata recorded.")
        lines.append("")

        lines.append("## Metrics")
        lines.append("")
        lines.append("| Dimension | Score |")
        lines.append("|-----------|-------|")
        lines.append(f"| Overall Risk | {risk_score:.1f}/100 |")

        n_findings = session.total_findings
        sev_counts: dict = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for sr in session.scan_results:
            for f in sr.findings:
                s = f.severity.value if isinstance(f.severity, Severity) else str(f.severity)
                sev_counts[s.lower()] = sev_counts.get(s.lower(), 0) + 1
        for sev_name in ("critical", "high", "medium", "low", "info"):
            if sev_counts.get(sev_name, 0) > 0:
                lines.append(f"| {sev_name.title()} Findings | {sev_counts[sev_name]} |")

        lines.extend(
            [
                "",
                "## Evaluation Data",
                "",
                f"{len(session.scan_results)} scanner(s) executed, "
                f"{n_findings} finding(s) across all scanners.",
                "",
            ]
        )
        for sr in session.scan_results:
            lines.append(
                f"- **{sr.scanner_name}** v{sr.scanner_version}: "
                f"{len(sr.findings)} finding(s), "
                f"severity {sr.overall_severity.value if isinstance(sr.overall_severity, Severity) else sr.overall_severity}"
            )

        lines.extend(
            [
                "",
                "## Quantitative Analyses",
                "",
            ]
        )
        if session.scan_results:
            for sr in session.scan_results:
                lines.append(f"### {sr.scanner_name}")
                if sr.error:
                    lines.append(f"- **Error**: {sr.error}")
                    continue
                lines.append(
                    f"- **Overall Severity**: {sr.overall_severity.value if isinstance(sr.overall_severity, Severity) else sr.overall_severity}"
                )
                lines.append(f"- **Findings**: {len(sr.findings)}")
                for f in sr.findings:
                    cwe = f" ({f.cwe_id})" if f.cwe_id else ""
                    mitre = f" (MITRE: {f.mitre_id})" if f.mitre_id else ""
                    nist = f" (NIST: {f.nist_id})" if f.nist_id else ""
                    refs = cwe + mitre + nist
                    lines.append(
                        f"  - **{f.title}** [{f.severity.value if isinstance(f.severity, Severity) else f.severity}]{refs}"
                    )
                    lines.append(f"    - {f.description}")
                    if f.recommendation:
                        lines.append(f"    - *Recommendation*: {f.recommendation}")
        else:
            lines.append("No scanner data available.")

        lines.extend(
            [
                "",
                "## Ethical Considerations",
                "",
            ]
        )
        ethics_findings = [
            f
            for sr in session.scan_results
            for f in sr.findings
            if f.title.lower().startswith(("bias", "toxicity", "fairness", "ethical"))
        ]
        if ethics_findings:
            for f in ethics_findings:
                lines.append(
                    f"- **{f.title}** [{f.severity.value if isinstance(f.severity, Severity) else f.severity}]: {f.description}"
                )
        else:
            lines.append("No ethics-specific scans were run, or no ethics findings were detected.")
        lines.append("")

        interp_summaries = [r.summary for r in session.interpret_results if r.summary]
        if interp_summaries:
            lines.extend(
                [
                    "## Interpretability",
                    "",
                ]
            )
            for summary in interp_summaries:
                lines.append(f"- {summary}")
            lines.append("")

        lines.extend(
            [
                "## Caveats and Recommendations",
                "",
            ]
        )
        recommendations = []
        for sr in session.scan_results:
            for f in sr.findings:
                if f.recommendation and f.recommendation not in recommendations:
                    recommendations.append(f.recommendation)
        if recommendations:
            for r in recommendations[:5]:
                lines.append(f"- {r}")
        else:
            lines.append("No specific recommendations recorded.")

        lines.append("")
        return "\n".join(lines)

    def _markdown_to_html(
        self,
        header_md: str,
        scan_md: str,
        interp_md: str,
        risk_score: float,
        risk_level: str,
        session,
    ) -> str:
        def _md_to_html(text: str) -> str:
            lines_out = []
            for line in text.split("\n"):
                stripped = line.strip()
                if not stripped:
                    lines_out.append("<br>")
                elif stripped.startswith("###"):
                    lines_out.append(f"<h3>{stripped.lstrip('# ')}</h3>")
                elif stripped.startswith("##"):
                    lines_out.append(f"<h2>{stripped.lstrip('# ')}</h2>")
                elif stripped.startswith("#"):
                    lines_out.append(f"<h1>{stripped.lstrip('# ')}</h1>")
                elif stripped.startswith("- "):
                    lines_out.append(f"<li>{stripped[2:]}</li>")
                else:
                    rendered = stripped.replace("**", "<strong>").replace("\n", "<br>")
                    lines_out.append(f"<p>{rendered}</p>")
            return "".join(lines_out)

        risk_class = (
            f"severity-{risk_level}"
            if risk_level in ("critical", "high", "medium", "low", "info")
            else "severity-info"
        )
        total_findings = session.total_findings if hasattr(session, "total_findings") else 0

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Security Audit Report - {session.session_id}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 960px; margin: 0 auto; padding: 2rem; background: #f9fafb; color: #111827; }}
  h1 {{ color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }}
  h2 {{ color: #1f2937; margin-top: 2rem; }}
  h3 {{ color: #374151; margin-top: 1.5rem; }}
  .header {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; }}
  .header p {{ margin: 0.25rem 0; }}
  .risk-badge {{ display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; color: white; font-weight: 600; font-size: 0.875rem; }}
  .severity-critical {{ background: #dc2626; }} .severity-high {{ background: #ea580c; }} .severity-medium {{ background: #ca8a04; }} .severity-low {{ background: #16a34a; }} .severity-info {{ background: #2563eb; }}
  .finding {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
  hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 1.5rem 0; }}
</style>
</head>
<body>
  <div class="header">
    {_md_to_html(header_md)}
    <p><strong>Risk Score:</strong> <span class="risk-badge {risk_class}">{risk_score:.1f} ({risk_level})</span></p>
    <p><strong>Total Findings:</strong> {total_findings}</p>
  </div>
  <h2>Scan Results</h2>
  {_md_to_html(scan_md)}
  <h2>Interpretation Results</h2>
  {_md_to_html(interp_md)}
</body>
</html>"""

    def _scanner_risk(self, result: "ScanResult") -> float:
        if not result.findings:
            return 0.0
        weights = {
            "critical": 1.00,
            "high": 0.80,
            "medium": 0.55,
            "low": 0.30,
            "info": 0.10,
            "unknown": 0.0,
        }
        scores = []
        for f in result.findings:
            sev = getattr(f.severity, "value", str(f.severity)).lower()
            conf = float(getattr(f, "confidence", 0.5) or 0.0)
            scores.append(weights.get(sev, 0.0) * max(0.0, min(conf, 1.0)))
        return round((sum(scores) / len(scores)) * 100.0, 2)

    def _session_risk(self, session: "AuditSession") -> float:
        if not session.scan_results:
            return 0.0
        scanner_scores = [self._scanner_risk(r) for r in session.scan_results]
        # Blend average risk with maximum risk to highlight worst-case scanners.
        avg_score = sum(scanner_scores) / len(scanner_scores)
        max_score = max(scanner_scores)
        return round((0.65 * avg_score) + (0.35 * max_score), 2)

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 75:
            return "critical"
        if score >= 55:
            return "high"
        if score >= 30:
            return "medium"
        if score >= 10:
            return "low"
        return "info"

    @staticmethod
    def _severity_tag(value: str) -> str:
        value = value.lower()
        if value == "critical":
            return "🔴"
        if value == "high":
            return "🟠"
        if value == "medium":
            return "🟡"
        if value == "low":
            return "🟢"
        return "⚪"

    @staticmethod
    def _truncate_text(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."
