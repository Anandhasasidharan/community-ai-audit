from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from .base import AgentScanner

log = logging.getLogger(__name__)


class ToolAbuseScanner(AgentScanner):
    """Detects tool abuse patterns in agent sessions.

    Analyzes tool call frequency, rate, repetition, and
    unusual tool usage patterns that may indicate abuse.
    """

    name = "tool_abuse"
    description = "Detect tool abuse patterns: excessive calls, repetition, rate anomalies"
    version = "0.1.0"

    SUSPICIOUS_TOOLS = {
        "exec",
        "eval",
        "exec_command",
        "run_shell",
        "subprocess",
        "file_write",
        "file_delete",
        "chmod",
        "curl",
        "wget",
        "rm",
        "dd",
        "mkfs",
        "mount",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.max_calls_per_minute = cfg.get("max_calls_per_minute", 30)
        self.max_repetitions = cfg.get("max_repetitions", 5)
        self.suspicious_tools = set(cfg.get("suspicious_tools", self.SUSPICIOUS_TOOLS))

    def scan(
        self,
        session: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if config:
            self.max_calls_per_minute = config.get(
                "max_calls_per_minute", self.max_calls_per_minute
            )
            self.max_repetitions = config.get("max_repetitions", self.max_repetitions)
            if "suspicious_tools" in config:
                self.suspicious_tools = set(config["suspicious_tools"])

        findings: List[Dict[str, Any]] = []
        tool_calls = [
            s
            for s in session.steps
            if getattr(s, "step_type", None) is not None and s.step_type.value == "tool_call"
        ]

        total_calls = len(tool_calls)
        if total_calls == 0:
            return {
                "scanner_name": self.name,
                "score": 100.0,
                "findings": [],
                "details": {
                    "total_tool_calls": 0,
                    "message": "No tool calls to analyze",
                },
            }

        tool_names = []
        for tc in tool_calls:
            inp = tc.input if isinstance(tc.input, dict) else {}
            tool_names.append(inp.get("tool", "unknown"))

        tool_counter = Counter(tool_names)
        most_common_tool, most_common_count = tool_counter.most_common(1)[0]

        if most_common_count > self.max_repetitions:
            findings.append(
                {
                    "severity": "medium",
                    "title": "Excessive tool repetition",
                    "description": (
                        f"Tool '{most_common_tool}' called {most_common_count} times "
                        f"(limit: {self.max_repetitions})"
                    ),
                    "tool": most_common_tool,
                    "count": most_common_count,
                }
            )

        suspicious_used = [t for t in tool_names if t in self.suspicious_tools]
        for tool in set(suspicious_used):
            count = suspicious_used.count(tool)
            findings.append(
                {
                    "severity": "high" if count > 1 else "medium",
                    "title": "Suspicious tool usage",
                    "description": f"Potentially dangerous tool '{tool}' called {count} time(s)",
                    "tool": tool,
                    "count": count,
                }
            )

        if tool_calls and total_calls > 1:
            timestamps = [tc.timestamp for tc in tool_calls if hasattr(tc, "timestamp")]
            if len(timestamps) >= 2:
                time_span = (timestamps[-1] - timestamps[0]).total_seconds()
                rate = total_calls / max(time_span / 60.0, 0.001)
                if rate > self.max_calls_per_minute:
                    findings.append(
                        {
                            "severity": "medium",
                            "title": "High tool call rate",
                            "description": (
                                f"Tool call rate {rate:.1f}/min exceeds "
                                f"limit of {self.max_calls_per_minute}/min"
                            ),
                            "rate": round(rate, 1),
                            "limit": self.max_calls_per_minute,
                        }
                    )

        uniq_tools = len(tool_counter)
        score = self._compute_score(findings, total_calls, uniq_tools)

        return {
            "scanner_name": self.name,
            "score": round(score, 1),
            "findings": findings,
            "details": {
                "total_tool_calls": total_calls,
                "unique_tools": uniq_tools,
                "tools_used": dict(tool_counter.most_common()),
                "suspicious_tools_found": list(set(suspicious_used)),
                "finding_count": len(findings),
            },
        }

    def _compute_score(
        self, findings: List[Dict[str, Any]], total_calls: int, uniq_tools: int
    ) -> float:
        score = 100.0
        for f in findings:
            sev = f.get("severity", "low").lower()
            if sev == "critical":
                score -= 25
            elif sev == "high":
                score -= 15
            elif sev == "medium":
                score -= 8
            elif sev == "low":
                score -= 3
        return max(0.0, score)
