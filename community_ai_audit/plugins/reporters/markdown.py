"""
Default Markdown report plugin.
This is the built-in reporter used for human-readable output.
"""

from typing import Any, Dict, Optional

from community_ai_audit.core.interfaces import ReporterPlugin
from community_ai_audit.reporting import ReportGenerator


class MarkdownReporter(ReporterPlugin):
    name = "markdown"
    supported_formats = ["markdown"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._generator = ReportGenerator(config=self.config)

    def render(self, scan_results, interpret_results, metadata):
        # Reuse the central report generator so all markdown stays consistent.
        session = _SessionShim(scan_results=scan_results, interpret_results=interpret_results, metadata=metadata)
        return self._generator.render_session(session, fmt="markdown")


class _SessionShim:
    def __init__(self, scan_results, interpret_results, metadata):
        self.session_id = metadata.get("session_id", "local")
        self.model_id = metadata.get("model_id")
        self.adapter_name = metadata.get("adapter_name")
        self.started_at = metadata.get("started_at")
        self.completed_at = metadata.get("completed_at")
        self.duration_seconds = metadata.get("duration_seconds", 0.0)
        self.scan_results = scan_results
        self.interpret_results = interpret_results
        self.connector_results = metadata.get("connector_results", {})

    @property
    def total_findings(self):
        return sum(len(r.findings) for r in self.scan_results)

    @property
    def highest_severity(self):
        from community_ai_audit.core.interfaces import Severity
        if not self.scan_results:
            return Severity.UNKNOWN
        return max((r.overall_severity for r in self.scan_results), key=lambda s: _severity_rank(s))


def _severity_rank(sev):
    from community_ai_audit.core.interfaces import Severity
    order = {
        Severity.CRITICAL: 4,
        Severity.HIGH: 3,
        Severity.MEDIUM: 2,
        Severity.LOW: 1,
        Severity.INFO: 0,
        Severity.UNKNOWN: -1,
    }
    return order.get(sev, -1)
