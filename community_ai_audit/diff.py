"""
Audit summary diff — compare two audit runs and highlight what changed.

Usage:
  from community_ai_audit.diff import audit_diff
  diff = audit_diff(session_a, session_b)
  print(diff.summary())
"""

from __future__ import annotations

from typing import Any, Dict, List

from community_ai_audit.core.interfaces import Finding, Severity


class AuditDiff:
    def __init__(
        self,
        session_a_id: str,
        session_b_id: str,
        new_findings: List[Finding],
        resolved_findings: List[Finding],
        changed_findings: List[Dict[str, Any]],
        severity_shifts: Dict[str, Dict[str, str]],
        metrics: Dict[str, Any],
    ):
        self.session_a_id = session_a_id
        self.session_b_id = session_b_id
        self.new_findings = new_findings
        self.resolved_findings = resolved_findings
        self.changed_findings = changed_findings
        self.severity_shifts = severity_shifts
        self.metrics = metrics

    @property
    def total_changes(self) -> int:
        return len(self.new_findings) + len(self.resolved_findings) + len(self.changed_findings)

    @property
    def severity_trend(self) -> str:
        """Return 'improved', 'worsened', or 'stable' based on severity shifts."""
        worsened = sum(
            1 for s in self.severity_shifts.values()
            if _severity_rank(s.get("old", Severity.UNKNOWN)) < _severity_rank(s.get("new", Severity.UNKNOWN))
        )
        improved = sum(
            1 for s in self.severity_shifts.values()
            if _severity_rank(s.get("old", Severity.UNKNOWN)) > _severity_rank(s.get("new", Severity.UNKNOWN))
        )
        if worsened > improved:
            return "worsened"
        if improved > worsened:
            return "improved"
        return "stable"

    def summary(self) -> str:
        trend = self.severity_trend
        return (
            f"Diff {self.session_a_id} → {self.session_b_id} | "
            f"{len(self.new_findings)} new, {len(self.resolved_findings)} resolved, "
            f"{len(self.changed_findings)} changed | severity: {trend}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_a": self.session_a_id,
            "session_b": self.session_b_id,
            "new_findings": [f.to_dict() for f in self.new_findings],
            "resolved_findings": [f.to_dict() for f in self.resolved_findings],
            "changed_findings": self.changed_findings,
            "severity_shifts": self.severity_shifts,
            "total_changes": self.total_changes,
            "severity_trend": self.severity_trend,
            "metrics": self.metrics,
        }


def _severity_rank(sev: Any) -> int:
    if isinstance(sev, str):
        sev = sev.lower()
        return {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0, "unknown": -1}.get(sev, -1)
    return {
        Severity.CRITICAL: 4, Severity.HIGH: 3, Severity.MEDIUM: 2, Severity.LOW: 1,
        Severity.INFO: 0, Severity.UNKNOWN: -1,
    }.get(sev, -1)


def _finding_key(finding: Finding) -> str:
    """Build a stable key for matching findings across runs."""
    return f"{finding.title}|{finding.cwe_id}|{finding.mitre_id or ''}"


def audit_diff(
    session_a: Any,
    session_b: Any,
    match_by: str = "title",
) -> AuditDiff:
    """Compare two AuditSessions and return a structured diff.

    Args:
        session_a: First AuditSession.
        session_b: Second AuditSession.
        match_by: How to match findings ('title' or 'key' which combines title+CWE+MITRE).

    Returns:
        AuditDiff with new, resolved, and changed findings.
    """
    from community_ai_audit.core.audit import AuditSession

    def _get_findings(session: AuditSession) -> List[Finding]:
        findings: List[Finding] = []
        for sr in session.scan_results:
            findings.extend(sr.findings)
        return findings

    findings_a = _get_findings(session_a)
    findings_b = _get_findings(session_b)

    if match_by == "key":
        key_fn = _finding_key
    else:
        def _key_by_title(f: Finding) -> str:
            return f.title
        key_fn = _key_by_title

    map_a: Dict[str, Finding] = {key_fn(f): f for f in findings_a}
    map_b: Dict[str, Finding] = {key_fn(f): f for f in findings_b}

    keys_a = set(map_a.keys())
    keys_b = set(map_b.keys())

    new_keys = keys_b - keys_a
    resolved_keys = keys_a - keys_b
    common_keys = keys_a & keys_b

    new_findings = [map_b[k] for k in sorted(new_keys)]
    resolved_findings = [map_a[k] for k in sorted(resolved_keys)]

    changed_findings: List[Dict[str, Any]] = []
    severity_shifts: Dict[str, Dict[str, str]] = {}

    for key in sorted(common_keys):
        f_a = map_a[key]
        f_b = map_b[key]

        changes: Dict[str, tuple] = {}
        if f_a.severity != f_b.severity:
            changes["severity"] = (f_a.severity.value, f_b.severity.value)
            severity_shifts[key] = {"old": f_a.severity.value, "new": f_b.severity.value}
        if f_a.confidence != f_b.confidence:
            changes["confidence"] = (f_a.confidence, f_b.confidence)

        if changes:
            changed_findings.append({
                "title": f_a.title,
                "changes": {k: {"from": v[0], "to": v[1]} for k, v in changes.items()},
            })

    metrics = {
        "findings_before": len(findings_a),
        "findings_after": len(findings_b),
        "scanner_count_before": len(session_a.scan_results),
        "scanner_count_after": len(session_b.scan_results),
        "highest_severity_a": session_a.highest_severity.value,
        "highest_severity_b": session_b.highest_severity.value,
    }

    return AuditDiff(
        session_a_id=session_a.session_id,
        session_b_id=session_b.session_id,
        new_findings=new_findings,
        resolved_findings=resolved_findings,
        changed_findings=changed_findings,
        severity_shifts=severity_shifts,
        metrics=metrics,
    )
