"""
Report generator — formats ScanResult, InterpretationResult, and AuditSession
into Markdown and JSON.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from community_ai_audit.core.audit import AuditSession

from community_ai_audit.core.interfaces import ScanResult, InterpretationResult


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

    def render_interpret_results(self, results: List["InterpretationResult"], fmt: str = "markdown") -> str:
        if fmt == "json":
            return json.dumps([r.to_dict() for r in results], indent=2, default=str)

        lines = []
        for result in results:
            lines.append(f"## Interpreter: {result.interpreter_name} (v{result.interpreter_version})")
            if result.error:
                lines.append(f"**Error:** {result.error}")
            else:
                lines.append(f"**Summary:** {result.summary}")
                if result.attributions:
                    lines.append(f"**Attributions (top):** {self._truncate_text(str(result.attributions), 1200)}")
            lines.append("\n---\n")

        return "\n".join(lines)

    def render_session(self, session: "AuditSession", fmt: str = "markdown") -> str:
        if fmt == "json":
            payload = session.to_dict()
            payload["risk_score"] = self._session_risk(session)
            payload["risk_level"] = self._risk_level(payload["risk_score"])
            return json.dumps(payload, indent=2, default=str)

        risk_score = self._session_risk(session)
        risk_level = self._risk_level(risk_score)

        lines = [
            "# 🤖 Community AI Security Audit Report",
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
        lines.append(self.render_scan_results(session.scan_results, fmt=fmt))
        lines.append(self.render_interpret_results(session.interpret_results, fmt=fmt))

        if session.connector_results:
            lines.append("\n## Connector Results")
            for name, status in session.connector_results.items():
                lines.append(f"- **{name}**: {status}")

        return "\n".join(lines)

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
