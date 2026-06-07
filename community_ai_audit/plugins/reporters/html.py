"""
Default HTML report plugin.
Generates a self-contained HTML report with embedded CSS.
"""

from typing import Any, Dict, Optional

from community_ai_audit.core.interfaces import ReporterPlugin
from community_ai_audit.reporting import ReportGenerator


class HTMLReporter(ReporterPlugin):
    name = "html"
    supported_formats = ["html"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._generator = ReportGenerator(config=self.config)

    def render(self, scan_results, interpret_results, metadata):
        markdown_body = self._generator.render_scan_results(scan_results, fmt="markdown")
        interpret_body = self._generator.render_interpret_results(interpret_results, fmt="markdown")
        return _wrap_html(markdown_body, interpret_body, metadata)


def _severity_color(sev: str) -> str:
    sev = sev.lower()
    if sev == "critical":
        return "#dc2626"
    if sev == "high":
        return "#ea580c"
    if sev == "medium":
        return "#ca8a04"
    if sev == "low":
        return "#16a34a"
    if sev == "info":
        return "#2563eb"
    return "#6b7280"


def _wrap_html(markdown_body: str, interpret_body: str, metadata: Dict[str, Any]) -> str:
    newline_char = "\n"
    session_id = metadata.get("session_id", "unknown")
    model_id = metadata.get("model_id", "unknown")
    risk_score = metadata.get("risk_score", 0)
    risk_level = metadata.get("risk_level", "unknown")
    total_findings = metadata.get("total_findings", 0)

    lines = markdown_body.split("\n")
    html_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            html_lines.append("<br>")
        elif stripped.startswith("###"):
            sev_text = stripped.lstrip("#").strip()
            html_lines.append(f"<h3>{sev_text}</h3>")
        elif stripped.startswith("##"):
            title = stripped.lstrip("#").strip()
            html_lines.append(f"<h2>{title}</h2>")
        elif stripped.startswith("**"):
            rendered = (
                stripped.replace("**", "<strong>", 1)
                .replace("**", "</strong>", 1)
                .replace("\n", "<br>")
            )
            html_lines.append(f"<p>{rendered}</p>")
        else:
            html_lines.append(f"<p>{stripped}</p>")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Security Audit Report - {session_id}</title>
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
  .finding h3 {{ margin-top: 0; }}
  .meta {{ color: #6b7280; font-size: 0.875rem; }}
  hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 1.5rem 0; }}
</style>
</head>
<body>
  <h1>AI Security Audit Report</h1>
  <div class="header">
    <p><strong>Session ID:</strong> {session_id}</p>
    <p><strong>Model:</strong> {model_id}</p>
    <p><strong>Total Findings:</strong> {total_findings}</p>
    <p><strong>Risk Score:</strong> <span class="risk-badge severity-{risk_level}">{risk_score} ({risk_level})</span></p>
  </div>
  <h2>Scan Results</h2>
  {''.join(html_lines)}
  <h2>Interpretation Results</h2>
  {interpret_body.replace('**', '<strong>').replace(newline_char, '<br>') if interpret_body else '<p>No interpretation results.</p>'}
</body>
</html>"""
    return html
