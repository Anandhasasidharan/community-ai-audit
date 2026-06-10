from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TrendPoint:
    timestamp: str
    value: float
    label: str = ""


@dataclass
class TrendLine:
    scanner_name: str
    points: List[TrendPoint] = field(default_factory=list)


class TrendAnalyzer:
    """Analyzes trends in agent audit history."""

    def __init__(self, history: List[Dict[str, Any]]):
        self.history = sorted(history, key=lambda r: r.get("timestamp", ""))

    def get_trend(self, scanner_name: str) -> TrendLine:
        points: List[TrendPoint] = []
        for record in self.history:
            for result in record.get("scanner_results", []):
                if result.get("scanner_name") == scanner_name:
                    points.append(
                        TrendPoint(
                            timestamp=record.get("timestamp", ""),
                            value=result.get("score", 0.0),
                            label=f"Session {record.get('session_id', '?')[:8]}",
                        )
                    )
        return TrendLine(scanner_name=scanner_name, points=points)

    def all_trends(self) -> Dict[str, TrendLine]:
        scanner_names = set()
        for record in self.history:
            for result in record.get("scanner_results", []):
                scanner_names.add(result.get("scanner_name", ""))
        return {name: self.get_trend(name) for name in sorted(scanner_names)}

    def overall_trend(self) -> TrendLine:
        points: List[TrendPoint] = []
        for record in self.history:
            points.append(
                TrendPoint(
                    timestamp=record.get("timestamp", ""),
                    value=record.get("overall_score", 0.0),
                    label=f"Session {record.get('session_id', '?')[:8]}",
                )
            )
        return TrendLine(scanner_name="overall", points=points)

    def trend_direction(self, scanner_name: str, window: int = 5) -> str:
        trend = self.get_trend(scanner_name)
        if len(trend.points) < 2:
            return "stable"
        recent = trend.points[-window:] if len(trend.points) >= window else trend.points
        if len(recent) < 2:
            return "stable"
        first_val = recent[0].value
        last_val = recent[-1].value
        diff = last_val - first_val
        if diff > 5:
            return "improving"
        if diff < -5:
            return "degrading"
        return "stable"

    def get_summary(self) -> Dict[str, Any]:
        trends = self.all_trends()
        return {
            "total_audits": len(self.history),
            "time_span": self._time_span(),
            "scanner_trends": {
                name: {
                    "direction": self.trend_direction(name),
                    "latest": line.points[-1].value if line.points else None,
                    "min": min(p.value for p in line.points) if line.points else None,
                    "max": max(p.value for p in line.points) if line.points else None,
                    "avg": (
                        sum(p.value for p in line.points) / len(line.points)
                        if line.points else None
                    ),
                }
                for name, line in trends.items()
            },
        }

    def _time_span(self) -> Optional[str]:
        if len(self.history) < 2:
            return None
        first = self.history[0].get("timestamp", "")
        last = self.history[-1].get("timestamp", "")
        try:
            t1 = datetime.fromisoformat(first)
            t2 = datetime.fromisoformat(last)
            days = (t2 - t1).days
            if days > 0:
                return f"{days} days"
            hours = (t2 - t1).total_seconds() / 3600
            return f"{hours:.1f} hours"
        except (ValueError, TypeError):
            return None
