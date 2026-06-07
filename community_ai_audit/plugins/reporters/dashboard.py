"""
Dashboard reporter — HTML with embedded Chart.js visualizations.

Features:
  - Severity distribution pie chart
  - Scanner risk score bar chart
  - Finding severity breakdown
  - Collapsible finding details
  - Responsive layout
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from community_ai_audit.core.interfaces import ReporterPlugin, ScanResult, InterpretationResult

_severity_colors = {
    "critical": "#dc2626",
    "high": "#ea580c",
    "medium": "#ca8a04",
    "low": "#16a34a",
    "info": "#2563eb",
    "unknown": "#6b7280",
}


def _severity_color(sev: str) -> str:
    return _severity_colors.get(sev.lower(), "#6b7280")


def _scanner_risk(result: ScanResult) -> float:
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
    return round((sum(scores) / len(scores)) * 100.0, 2) if scores else 0.0


def _build_dashboard_html(
    scan_results: List[ScanResult],
    interpret_results: List[InterpretationResult],
    metadata: Dict[str, Any],
) -> str:
    session_id = metadata.get("session_id", "unknown")
    model_id = metadata.get("model_id", "unknown")
    total_findings = metadata.get("total_findings", 0)
    risk_score = metadata.get("risk_score", 0)
    risk_level = metadata.get("risk_level", "unknown")
    started_at = metadata.get("started_at", "")
    duration = metadata.get("duration_seconds", 0)

    severity_counts: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for sr in scan_results:
        for f in sr.findings:
            sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            sev = sev.lower()
            if sev in severity_counts:
                severity_counts[sev] += 1

    scanner_data = []
    for sr in scan_results:
        risk = _scanner_risk(sr)
        scanner_data.append(
            {
                "name": sr.scanner_name,
                "risk": risk,
                "severity": (
                    sr.overall_severity.value
                    if hasattr(sr.overall_severity, "value")
                    else str(sr.overall_severity)
                ),
                "findings": len(sr.findings),
            }
        )

    scanner_colors = [_severity_color(s["severity"]) for s in scanner_data]
    findings_json = __import__("json").dumps(severity_counts)
    scanners_json = __import__("json").dumps(scanner_data)
    colors_json = __import__("json").dumps(scanner_colors)

    findings_rows = []
    for sr in scan_results:
        for f in sr.findings:
            sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            color = _severity_color(sev)
            findings_rows.append(f"""
            <div class="finding" style="border-left: 4px solid {color};">
              <div class="finding-header" onclick="this.nextElementSibling.classList.toggle('open')">
                <span class="severity-badge" style="background:{color}">{sev.upper()}</span>
                <strong>{f.title}</strong>
              </div>
              <div class="finding-body">
                <p>{f.description}</p>
                <div class="meta">
                  <span>Confidence: {(f.confidence * 100):.0f}%</span>
                  {f'<span>CWE: {f.cwe_id}</span>' if f.cwe_id else ''}
                  {f'<span>MITRE: {f.mitre_id}</span>' if f.mitre_id else ''}
                </div>
                {f'<p><em>Recommendation:</em> {f.recommendation}</p>' if f.recommendation else ''}
              </div>
            </div>""")

    interpret_rows = []
    for ir in interpret_results:
        if ir.error:
            interpret_rows.append(
                f"<div class='finding'><p><strong>{ir.interpreter_name}:</strong> Error — {ir.error}</p></div>"
            )
        else:
            interpret_rows.append(f"""
            <div class="finding">
              <strong>{ir.interpreter_name} (v{ir.interpreter_version})</strong>
              <p>{ir.summary or 'No summary'}</p>
            </div>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Security Audit Dashboard - {session_id}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; color: #111827; }}
  .dashboard {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; max-width: 1400px; margin: 0 auto; padding: 2rem; }}
  .header {{ grid-column: 1 / -1; background: linear-gradient(135deg, #1e3a5f, #2563eb); color: white; border-radius: 12px; padding: 2rem; }}
  .header h1 {{ font-size: 1.8rem; margin-bottom: 1rem; }}
  .header .stats {{ display: flex; gap: 2rem; flex-wrap: wrap; }}
  .header .stat {{ background: rgba(255,255,255,0.15); border-radius: 8px; padding: 0.75rem 1.25rem; }}
  .header .stat-value {{ font-size: 1.5rem; font-weight: 700; }}
  .header .stat-label {{ font-size: 0.8rem; opacity: 0.8; }}
  .card {{ background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .card h2 {{ font-size: 1.1rem; color: #374151; margin-bottom: 1rem; }}
  .card.full-width {{ grid-column: 1 / -1; }}
  .finding {{ background: #f9fafb; border-radius: 8px; margin: 0.75rem 0; overflow: hidden; }}
  .finding-header {{ padding: 0.75rem 1rem; cursor: pointer; display: flex; align-items: center; gap: 0.75rem; }}
  .finding-header:hover {{ background: #f3f4f6; }}
  .finding-body {{ display: none; padding: 0 1rem 0.75rem; }}
  .finding-body.open {{ display: block; }}
  .severity-badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; color: white; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.05em; min-width: 4rem; text-align: center; }}
  .meta {{ display: flex; gap: 1rem; font-size: 0.8rem; color: #6b7280; margin-top: 0.5rem; }}
  .risk-bar {{ height: 8px; border-radius: 4px; background: #e5e7eb; margin-top: 0.5rem; }}
  .risk-fill {{ height: 100%; border-radius: 4px; transition: width 0.5s; }}
  .chart-container {{ position: relative; height: 250px; }}
  @media (max-width: 768px) {{ .dashboard {{ grid-template-columns: 1fr; }} .header {{ grid-column: 1; }} .card.full-width {{ grid-column: 1; }} }}
</style>
</head>
<body>
<div class="dashboard">
  <div class="header">
    <h1>AI Security Audit Dashboard</h1>
    <div class="stats">
      <div class="stat"><div class="stat-value">{total_findings}</div><div class="stat-label">Findings</div></div>
      <div class="stat"><div class="stat-value" style="color:{_severity_color(risk_level)}">{risk_score:.1f}</div><div class="stat-label">Risk Score ({risk_level})</div></div>
      <div class="stat"><div class="stat-value">{len(scan_results)}</div><div class="stat-label">Scanners</div></div>
      <div class="stat"><div class="stat-value">{len(interpret_results)}</div><div class="stat-label">Interpreters</div></div>
      <div class="stat"><div class="stat-value">{duration:.1f}s</div><div class="stat-label">Duration</div></div>
    </div>
    <div style="margin-top:1rem; font-size:0.85rem; opacity:0.9;">
      Session: {session_id} &middot; Model: {model_id} &middot; {started_at}
    </div>
  </div>

  <div class="card">
    <h2>Severity Distribution</h2>
    <div class="chart-container">
      <canvas id="severityChart"></canvas>
    </div>
  </div>

  <div class="card">
    <h2>Scanner Risk Scores</h2>
    <div class="chart-container">
      <canvas id="scannerChart"></canvas>
    </div>
  </div>

  <div class="card full-width">
    <h2>Scanner Details</h2>
    {''.join(f'''
    <div class="finding" style="margin-bottom:0.5rem;">
      <div class="finding-header" onclick="this.nextElementSibling.classList.toggle('open')">
        <span class="severity-badge" style="background:{_severity_color(s['severity'])}">{s['severity'].upper()}</span>
        <strong>{s['name']}</strong>
        <span style="margin-left:auto;color:#6b7280;font-size:0.85rem;">{s['findings']} findings &middot; {s['risk']:.1f}/100</span>
      </div>
      <div class="finding-body">
        <div class="risk-bar"><div class="risk-fill" style="width:{s['risk']}%;background:{_severity_color(s['severity'])}"></div></div>
      </div>
    </div>''' for s in scanner_data)}
  </div>

  <div class="card full-width">
    <h2>Findings</h2>
    {''.join(findings_rows) if findings_rows else '<p style="color:#6b7280;">No findings.</p>'}
  </div>

  {'<div class="card full-width"><h2>Interpretation Results</h2>' + ''.join(interpret_rows) + '</div>' if interpret_rows else ''}
</div>

<script>
const severityData = {findings_json};
new Chart(document.getElementById('severityChart'), {{
  type: 'doughnut',
  data: {{
    labels: Object.keys(severityData).filter(k => severityData[k] > 0),
    datasets: [{{
      data: Object.values(severityData).filter(v => v > 0),
      backgroundColor: ['#dc2626','#ea580c','#ca8a04','#16a34a','#2563eb'],
    }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ position: 'right' }} }} }}
}});

const scannerData = {scanners_json};
const scannerColors = {colors_json};
new Chart(document.getElementById('scannerChart'), {{
  type: 'bar',
  data: {{
    labels: scannerData.map(s => s.name),
    datasets: [{{
      label: 'Risk Score',
      data: scannerData.map(s => s.risk),
      backgroundColor: scannerColors,
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    scales: {{ y: {{ beginAtZero: true, max: 100 }} }},
    plugins: {{ legend: {{ display: false }} }}
  }}
}});
</script>
</body>
</html>"""


class DashboardReporter(ReporterPlugin):
    name = "dashboard"
    supported_formats = ["dashboard"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def render(
        self,
        scan_results: List[ScanResult],
        interpret_results: List[InterpretationResult],
        metadata: Dict[str, Any],
    ) -> str:
        return _build_dashboard_html(scan_results, interpret_results, metadata)
