"""JSON report format."""

from typing import Any
import json

from community_ai_audit.reporting.generator import ReportGenerator


class JSONReporter:
    """JSON report format plugin."""

    @classmethod
    def render(cls, session: Any) -> str:
        gen = ReportGenerator()
        payload = session.to_dict()
        payload["risk_score"] = gen._session_risk(session)
        payload["risk_level"] = gen._risk_level(payload["risk_score"])
        return json.dumps(payload, indent=2, default=str)
