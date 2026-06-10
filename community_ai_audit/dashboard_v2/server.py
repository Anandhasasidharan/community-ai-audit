from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from community_ai_audit.monitoring import (
    AgentAuditor,
    MonitorConfig,
    TrendAnalyzer,
    DriftDetector,
    AlertManager,
)


@dataclass
class DashboardConfig:
    title: str = "Community AI Audit - Agent Monitoring"
    refresh_seconds: int = 60
    history_limit: int = 100
    drift_baseline_window: int = 20
    storage_dir: str = os.path.expanduser("~/.community-ai-audit/monitoring")


class DashboardServer:
    """Generates HTML monitoring dashboards for agent audit data."""

    def __init__(self, config: Optional[DashboardConfig] = None):
        self.config = config or DashboardConfig()
        monitor_config = MonitorConfig(
            storage_dir=self.config.storage_dir,
            max_history=self.config.history_limit,
        )
        self.auditor = AgentAuditor(config=monitor_config)
        self.alert_manager = AlertManager()

    def render_html(self) -> str:
        history = self.auditor.get_history(limit=self.config.history_limit)
        trend_analyzer = TrendAnalyzer(history)
        drift_detector = DriftDetector()

        baseline_records = history[: self.config.drift_baseline_window] if len(history) > self.config.drift_baseline_window else history
        current_records = history[-10:] if len(history) >= 10 else history
        drift_reports = drift_detector.detect_drift(baseline_records, current_records) if history else []

        alerts = self.alert_manager.get_alerts(limit=20)
        trends = trend_analyzer.get_summary()
        overall_trend = trend_analyzer.overall_trend()

        latest_overall = overall_trend.points[-1].value if overall_trend.points else 100.0
        security_score = self._get_latest_scanner_score(history, "tool_abuse")
        reliability_score = self._get_latest_scanner_score(history, "memory_poisoning")
        compliance_score = self._get_latest_scanner_score(history, "goal_drift")
        agent_risk_score = self._get_latest_scanner_score(history, "unsafe_action") or latest_overall
        alignment_score = self._get_latest_scanner_score(history, "sycophancy") or 100.0
        red_team_score = self._get_latest_scanner_score(history, "jailbreak") or 100.0
        interpretability_score = self._get_latest_scanner_score(history, "activation_probes") or 50.0

        scanner_trends = trend_analyzer.all_trends()

        return self._build_html(
            latest_overall=latest_overall,
            security_score=security_score,
            reliability_score=reliability_score,
            compliance_score=compliance_score,
            agent_risk_score=agent_risk_score,
            alignment_score=alignment_score,
            red_team_score=red_team_score,
            interpretability_score=interpretability_score,
            drift_reports=drift_reports,
            alerts=alerts,
            trend_summary=trends,
            scanner_trends=scanner_trends,
            total_audits=len(history),
            overall_trend=overall_trend,
        )

    def _get_latest_scanner_score(self, history, name):
        for record in reversed(history):
            for result in record.get("scanner_results", []):
                if result.get("scanner_name") == name:
                    return result.get("score", 100.0)
        return 100.0

    def _score_to_rating(self, score: float) -> str:
        if score >= 90:
            return "Excellent"
        if score >= 80:
            return "Good"
        if score >= 70:
            return "Fair"
        if score >= 60:
            return "Poor"
        return "Critical"

    def _score_color(self, score: float) -> str:
        if score >= 80:
            return "#4CAF50"
        if score >= 60:
            return "#FF9800"
        return "#f44336"

    def _build_html(
        self,
        latest_overall: float,
        security_score: float,
        reliability_score: float,
        compliance_score: float,
        agent_risk_score: float,
        alignment_score: float,
        red_team_score: float,
        interpretability_score: float,
        drift_reports: list,
        alerts: list,
        trend_summary: dict,
        scanner_trends: dict,
        total_audits: int,
        overall_trend: Any,
    ) -> str:
        scanners_table = ""
        for name, line in scanner_trends.items():
            pts = [(p.value) for p in line.points[-10:]]
            latest_val = pts[-1] if pts else 100.0
            color = self._score_color(latest_val)
            sparkline = f"[{', '.join(str(round(v, 1)) for v in pts[-20:])}]" if pts else "[]"
            direction = trend_summary.get("scanner_trends", {}).get(name, {}).get("direction", "stable")
            dir_icon = "▲" if direction == "improving" else "▼" if direction == "degrading" else "◆"
            dir_color = "#4CAF50" if direction == "improving" else "#f44336" if direction == "degrading" else "#999"
            scanners_table += f"""
            <tr>
                <td>{name}</td>
                <td style="color: {color}; font-weight: bold;">{latest_val:.1f}</td>
                <td style="color: {dir_color};">{dir_icon} {direction}</td>
                <td style="font-size: 12px; color: #666; font-family: monospace;">{sparkline}</td>
            </tr>"""

        drift_rows = ""
        for dr in drift_reports:
            color = "#f44336" if dr.drifted else "#4CAF50"
            icon = "⚠" if dr.drifted else "✓"
            drift_rows += f"""
            <tr>
                <td>{dr.scanner_name}</td>
                <td>{dr.baseline_score:.1f}</td>
                <td>{dr.current_score:.1f}</td>
                <td style="color: {'#f44336' if dr.delta < 0 else '#4CAF50'};">{dr.delta:+.1f}</td>
                <td style="color: {color};">{icon} {'Drifted' if dr.drifted else 'Stable'}</td>
            </tr>"""

        alerts_html = ""
        for alert in alerts[:10]:
            color = {"info": "#2196F3", "warning": "#FF9800", "critical": "#f44336"}
            alerts_html += f"""
            <div class="alert" style="border-left: 4px solid {color.get(alert.level.value, '#999')};">
                <strong>{alert.title}</strong>
                <p>{alert.message}</p>
                <span class="alert-time">{alert.timestamp[:19]}</span>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{self.config.title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f23; color: #e0e0e0; padding: 20px; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  .header {{ margin-bottom: 30px; }}
  .header h1 {{ font-size: 28px; color: #fff; margin-bottom: 8px; }}
  .header p {{ color: #888; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
  .card {{ background: #1a1a2e; border-radius: 12px; padding: 20px; border: 1px solid #2a2a4e; }}
  .card h3 {{ font-size: 13px; text-transform: uppercase; color: #888; margin-bottom: 8px; letter-spacing: 0.5px; }}
  .card .score {{ font-size: 36px; font-weight: bold; margin-bottom: 4px; }}
  .card .rating {{ font-size: 14px; }}
  .section {{ background: #1a1a2e; border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid #2a2a4e; }}
  .section h2 {{ font-size: 18px; margin-bottom: 15px; color: #fff; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #2a2a4e; font-size: 14px; }}
  th {{ color: #888; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
  td {{ color: #ccc; }}
  .alert {{ background: #1a1a2e; padding: 12px 16px; margin: 8px 0; border-radius: 8px; border: 1px solid #2a2a4e; }}
  .alert strong {{ display: block; margin-bottom: 4px; }}
  .alert p {{ font-size: 13px; color: #999; margin-bottom: 4px; }}
  .alert-time {{ font-size: 11px; color: #666; }}
  .trend-chart {{ background: #16213e; border-radius: 8px; padding: 15px; margin-top: 15px; font-family: monospace; font-size: 13px; line-height: 1.6; white-space: pre; overflow-x: auto; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>{self.config.title}</h1>
    <p>{total_audits} total audits tracked | Auto-refresh every {self.config.refresh_seconds}s</p>
  </div>

  <div class="cards">
    <div class="card">
      <h3>Agent Risk</h3>
      <div class="score" style="color: {self._score_color(agent_risk_score)};">{agent_risk_score:.0f}</div>
      <div class="rating" style="color: {self._score_color(agent_risk_score)};">{self._score_to_rating(agent_risk_score)}</div>
    </div>
    <div class="card">
      <h3>Security</h3>
      <div class="score" style="color: {self._score_color(security_score)};">{security_score:.0f}</div>
      <div class="rating" style="color: {self._score_color(security_score)};">{self._score_to_rating(security_score)}</div>
    </div>
    <div class="card">
      <h3>Reliability</h3>
      <div class="score" style="color: {self._score_color(reliability_score)};">{reliability_score:.0f}</div>
      <div class="rating" style="color: {self._score_color(reliability_score)};">{self._score_to_rating(reliability_score)}</div>
    </div>
    <div class="card">
      <h3>Compliance</h3>
      <div class="score" style="color: {self._score_color(compliance_score)};">{compliance_score:.0f}</div>
      <div class="rating" style="color: {self._score_color(compliance_score)};">{self._score_to_rating(compliance_score)}</div>
    </div>
    <div class="card">
      <h3>Alignment</h3>
      <div class="score" style="color: {self._score_color(alignment_score)};">{alignment_score:.0f}</div>
      <div class="rating" style="color: {self._score_color(alignment_score)};">{self._score_to_rating(alignment_score)}</div>
    </div>
    <div class="card">
      <h3>Red Team Risk</h3>
      <div class="score" style="color: {self._score_color(red_team_score)};">{red_team_score:.0f}</div>
      <div class="rating" style="color: {self._score_color(red_team_score)};">{self._score_to_rating(red_team_score)}</div>
    </div>
    <div class="card">
      <h3>Interpretability</h3>
      <div class="score" style="color: {self._score_color(interpretability_score)};">{interpretability_score:.0f}</div>
      <div class="rating" style="color: {self._score_color(interpretability_score)};">{self._score_to_rating(interpretability_score)}</div>
    </div>
  </div>

  <div class="section">
    <h2>Overall Trend</h2>
    <div class="trend-chart">{self._render_ascii_chart(overall_trend)}</div>
  </div>

  <div class="section">
    <h2>Scanner Scores</h2>
    <table>
      <tr><th>Scanner</th><th>Latest Score</th><th>Trend</th><th>History (last 20)</th></tr>
      {scanners_table}
    </table>
  </div>

  <div class="section">
    <h2>Drift Detection</h2>
    <table>
      <tr><th>Scanner</th><th>Baseline</th><th>Current</th><th>Delta</th><th>Status</th></tr>
      {drift_rows if drift_rows else '<tr><td colspan="5" style="text-align:center; color:#666;">No drift data available (need at least 2 audit records)</td></tr>'}
    </table>
  </div>

  <div class="section">
    <h2>Recent Alerts</h2>
    {alerts_html if alerts_html else '<p style="color:#666;">No alerts</p>'}
  </div>

  <div class="section">
    <h2>Scanner Trend Summary</h2>
    <table>
      <tr><th>Scanner</th><th>Direction</th><th>Latest</th><th>Avg</th><th>Min</th><th>Max</th></tr>
      {self._render_trend_summary_rows(trend_summary)}
    </table>
  </div>
</div>
</body>
</html>"""

    def _render_ascii_chart(self, trend_line) -> str:
        values = [p.value for p in trend_line.points[-30:]]
        if not values:
            return "No data"

        min_v = min(values)
        max_v = max(values)
        rng = max_v - min_v if max_v != min_v else 1
        height = 8
        lines = ["" for _ in range(height)]
        step = rng / height

        for i in range(height):
            threshold = max_v - (i * step)
            bar = ""
            for v in values:
                if v >= threshold:
                    bar += "█"
                else:
                    bar += " "
            lines[i] = f"{max_v - i * step:6.0f} │ {bar}"

        return "\n".join(lines) + f"\n{'':6} └{'─' * len(values)}"

    def _render_trend_summary_rows(self, summary: Dict[str, Any]) -> str:
        rows = ""
        scanner_trends = summary.get("scanner_trends", {})
        for name, data in scanner_trends.items():
            direction = data.get("direction", "stable")
            dir_icon = "▲" if direction == "improving" else "▼" if direction == "degrading" else "◆"
            dir_color = "#4CAF50" if direction == "improving" else "#f44336" if direction == "degrading" else "#999"
            latest = data.get("latest", "N/A")
            avg = data.get("avg", "N/A")
            mn = data.get("min", "N/A")
            mx = data.get("max", "N/A")
            latest_str = f"{latest:.1f}" if latest is not None else "N/A"
            avg_str = f"{avg:.1f}" if avg is not None else "N/A"
            mn_str = f"{mn:.1f}" if mn is not None else "N/A"
            mx_str = f"{mx:.1f}" if mx is not None else "N/A"
            rows += f"""
            <tr>
                <td>{name}</td>
                <td style="color: {dir_color};">{dir_icon} {direction}</td>
                <td>{latest_str}</td>
                <td>{avg_str}</td>
                <td>{mn_str}</td>
                <td>{mx_str}</td>
            </tr>"""
        return rows

    def render_json(self) -> str:
        history = self.auditor.get_history(limit=self.config.history_limit)
        trend_analyzer = TrendAnalyzer(history)
        drift_detector = DriftDetector()

        baseline_records = history[: self.config.drift_baseline_window] if len(history) > self.config.drift_baseline_window else history
        current_records = history[-10:] if len(history) >= 10 else history
        drift_reports = drift_detector.detect_drift(baseline_records, current_records) if history else []

        alerts = self.alert_manager.get_alerts(limit=20)
        trends = trend_analyzer.get_summary()

        data = {
            "total_audits": len(history),
            "drift_reports": [r.to_dict() for r in drift_reports],
            "alerts": [a.to_dict() for a in alerts],
            "trend_summary": trends,
        }
        return json.dumps(data, indent=2, default=str)

    def save_html(self, path: str) -> str:
        html = self.render_html()
        with open(path, "w") as f:
            f.write(html)
        return path

    def save_json(self, path: str) -> str:
        data = self.render_json()
        with open(path, "w") as f:
            f.write(data)
        return path
