from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .models import ExecutionTrace


class TraceExporter:
    """Exports execution traces to various formats."""

    def __init__(self, trace: ExecutionTrace):
        self.trace = trace

    def to_json(self, indent: int = 2) -> str:
        return self.trace.to_json(indent=indent)

    def to_jsonl(self) -> str:
        lines: List[str] = []
        for step in self.trace.steps:
            lines.append(json.dumps(step.to_dict(), default=str))
        return "\n".join(lines)

    def to_html(self, title: Optional[str] = None) -> str:
        title = title or f"Execution Trace: {self.trace.session_id}"
        steps_html = ""
        for step in self.trace.steps:
            sd = step.to_dict()
            steps_html += f"""
            <div class="step {sd['step_type']}">
                <div class="step-header">
                    <span class="step-num">#{sd['step']}</span>
                    <span class="step-type">{sd['step_type']}</span>
                    <span class="step-duration">{sd['duration']}s</span>
                </div>
                <div class="step-detail">
                    <strong>Input:</strong> <pre>{self._escape(str(sd['input']))}</pre>
                    <strong>Output:</strong> <pre>{self._escape(str(sd['output']))}</pre>
                </div>
            </div>"""

        tool_calls = len(self.trace.tool_calls)
        decisions = len(self.trace.decisions)
        actions = len(self.trace.actions)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background: #f5f5f5; }}
  .trace {{ max-width: 900px; margin: auto; }}
  .header {{ background: #1a1a2e; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
  .header h1 {{ margin: 0 0 8px 0; }}
  .stats {{ display: flex; gap: 15px; margin: 15px 0; flex-wrap: wrap; }}
  .stat {{ background: white; padding: 15px; border-radius: 8px; flex: 1; min-width: 100px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }}
  .stat-value {{ font-size: 24px; font-weight: bold; color: #1a1a2e; }}
  .stat-label {{ font-size: 12px; color: #666; text-transform: uppercase; margin-top: 4px; }}
  .step {{ background: white; margin: 10px 0; padding: 15px; border-radius: 8px; border-left: 4px solid #ccc; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .step.tool_call {{ border-left-color: #4CAF50; }}
  .step.memory_access {{ border-left-color: #2196F3; }}
  .step.decision {{ border-left-color: #FF9800; }}
  .step.action {{ border-left-color: #f44336; }}
  .step.prompt {{ border-left-color: #9C27B0; }}
  .step.response {{ border-left-color: #00BCD4; }}
  .step-header {{ display: flex; gap: 15px; align-items: center; margin-bottom: 8px; }}
  .step-num {{ font-weight: bold; color: #666; }}
  .step-type {{ background: #e0e0e0; padding: 2px 8px; border-radius: 4px; font-size: 11px; text-transform: uppercase; }}
  .step-duration {{ margin-left: auto; color: #999; font-size: 12px; }}
  .step-detail pre {{ background: #f8f8f8; padding: 8px; border-radius: 4px; overflow-x: auto; font-size: 13px; margin: 4px 0; }}
</style>
</head>
<body>
<div class="trace">
  <div class="header">
    <h1>{title}</h1>
    <p>Agent: {self.trace.agent_id} | Session: {self.trace.session_id}</p>
    <p>Wall Clock: {self.trace.duration:.1f}s | Steps: {self.trace.step_count}</p>
  </div>
  <div class="stats">
    <div class="stat"><div class="stat-value">{tool_calls}</div><div class="stat-label">Tool Calls</div></div>
    <div class="stat"><div class="stat-value">{decisions}</div><div class="stat-label">Decisions</div></div>
    <div class="stat"><div class="stat-value">{actions}</div><div class="stat-label">Actions</div></div>
    <div class="stat"><div class="stat-value">{self.trace.step_count}</div><div class="stat-label">Total Steps</div></div>
  </div>
  {steps_html}
</div>
</body>
</html>"""

    def _escape(self, text: str) -> str:
        return (
            text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        )

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# Execution Trace: {self.trace.session_id}")
        lines.append(f"**Agent:** {self.trace.agent_id}")
        lines.append(f"**Steps:** {self.trace.step_count} | **Duration:** {self.trace.duration:.1f}s")
        lines.append("")
        lines.append("| Step | Type | Duration | Summary |")
        lines.append("|------|------|----------|---------|")
        for step in self.trace.steps:
            sd = step.to_dict()
            summary = str(sd.get("input", ""))[:60]
            lines.append(f"| {sd['step']} | {sd['step_type']} | {sd['duration']}s | {summary} |")
        lines.append("")
        return "\n".join(lines)

    def save(self, path: str, fmt: Optional[str] = None) -> None:
        if fmt is None:
            if path.endswith(".json"):
                fmt = "json"
            elif path.endswith(".jsonl"):
                fmt = "jsonl"
            elif path.endswith(".html"):
                fmt = "html"
            elif path.endswith(".md"):
                fmt = "markdown"
            else:
                fmt = "json"

        content = {
            "json": self.to_json,
            "jsonl": self.to_jsonl,
            "html": self.to_html,
            "markdown": self.to_markdown,
        }[fmt]()

        with open(path, "w") as f:
            f.write(content)
