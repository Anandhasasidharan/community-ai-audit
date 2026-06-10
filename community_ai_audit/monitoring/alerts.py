from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    title: str
    message: str
    level: AlertLevel = AlertLevel.WARNING
    source: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "message": self.message,
            "level": self.level.value,
            "source": self.source,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


DEFAULT_ALERT_STORAGE = os.path.expanduser("~/.community-ai-audit/monitoring/alerts.jsonl")


class AlertManager:
    """Manages alerts for agent monitoring.

    Supports creating, storing, querying, and acknowledging alerts
    from agent audit and drift detection.
    """

    def __init__(self, storage_path: str = DEFAULT_ALERT_STORAGE):
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)

    def emit(self, alert: Alert) -> None:
        log.log(
            {"info": 20, "warning": 30, "critical": 40}.get(alert.level.value, 30),
            "[%s] %s: %s",
            alert.level.value.upper(),
            alert.source,
            alert.message,
        )
        self._save(alert)

    def emit_from_audit(
        self,
        source: str,
        score: float,
        threshold: float,
        scanner_name: str,
        session_id: str,
    ) -> None:
        level = AlertLevel.CRITICAL if score < threshold * 0.5 else AlertLevel.WARNING
        self.emit(
            Alert(
                title=f"Score below threshold: {scanner_name}",
                message=(
                    f"Scanner '{scanner_name}' scored {score:.1f} "
                    f"(threshold: {threshold:.1f}) in session {session_id[:8]}"
                ),
                level=level,
                source=source,
                metadata={
                    "scanner_name": scanner_name,
                    "score": score,
                    "threshold": threshold,
                    "session_id": session_id,
                },
            )
        )

    def emit_from_drift(
        self,
        report: Any,
        source: str = "drift_detector",
    ) -> None:
        level = (
            AlertLevel.CRITICAL if abs(report.delta) > report.threshold * 2 else AlertLevel.WARNING
        )
        direction = "degraded" if report.delta < 0 else "improved"
        self.emit(
            Alert(
                title=f"Drift detected: {report.scanner_name}",
                message=(
                    f"Scanner '{report.scanner_name}' {direction} by "
                    f"{abs(report.delta):.1f} points "
                    f"({report.baseline_score:.1f} -> {report.current_score:.1f})"
                ),
                level=level,
                source=source,
                metadata={
                    "scanner_name": report.scanner_name,
                    "baseline_score": report.baseline_score,
                    "current_score": report.current_score,
                    "delta": report.delta,
                },
            )
        )

    def get_alerts(
        self,
        limit: int = 50,
        level: Optional[AlertLevel] = None,
        source: Optional[str] = None,
    ) -> List[Alert]:
        alerts: List[Alert] = []
        if not os.path.exists(self.storage_path):
            return alerts

        with open(self.storage_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    alert = Alert(
                        title=data["title"],
                        message=data["message"],
                        level=AlertLevel(data.get("level", "warning")),
                        source=data.get("source", ""),
                        timestamp=data.get("timestamp", ""),
                        metadata=data.get("metadata", {}),
                    )
                    if level and alert.level != level:
                        continue
                    if source and alert.source != source:
                        continue
                    alerts.append(alert)
                except (json.JSONDecodeError, KeyError):
                    continue
                if len(alerts) >= limit:
                    break

        return alerts

    def clear_alerts(self) -> int:
        count = 0
        if os.path.exists(self.storage_path):
            count = sum(1 for _ in open(self.storage_path))
            os.remove(self.storage_path)
        return count

    def _save(self, alert: Alert) -> None:
        with open(self.storage_path, "a") as f:
            f.write(json.dumps(alert.to_dict(), default=str) + "\n")
