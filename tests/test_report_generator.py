"""Tests for ReportGenerator — the report formatting engine."""

import unittest
from datetime import datetime, timezone

from community_ai_audit.reporting.generator import ReportGenerator
from community_ai_audit.core.interfaces import (
    ScanResult,
    InterpretationResult,
    Finding,
    Severity,
)


class _FakeSession:
    def __init__(self, scan_results=None, interpret_results=None, connector_results=None, metadata=None):
        self.session_id = "test-session"
        self.model_id = "test-model"
        self.adapter_name = "local"
        self.started_at = datetime.now(timezone.utc)
        self.completed_at = datetime.now(timezone.utc)
        self.duration_seconds = 1.5
        self.scan_results = scan_results or []
        self.interpret_results = interpret_results or []
        self.connector_results = connector_results or {}
        self.metadata = metadata or {"key": "value"}

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "model_id": self.model_id,
            "adapter_name": self.adapter_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "total_findings": self.total_findings,
            "highest_severity": self.highest_severity.value if hasattr(self.highest_severity, "value") else str(self.highest_severity),
            "scan_results": [r.to_dict() for r in self.scan_results],
            "interpret_results": [r.to_dict() for r in self.interpret_results],
            "connector_results": self.connector_results,
            "metadata": self.metadata,
        }

    @property
    def total_findings(self):
        return sum(len(r.findings) for r in self.scan_results)

    @property
    def highest_severity(self):
        if not self.scan_results:
            return Severity.UNKNOWN
        return max((r.overall_severity for r in self.scan_results), key=lambda s: _rank(s))


def _rank(s):
    return {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}.get(s.value.lower(), -1)


class TestReportGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = ReportGenerator()
        self.finding = Finding(
            title="Test Finding",
            description="A test vulnerability",
            severity=Severity.HIGH,
            confidence=0.85,
            evidence={"layer": "fc1"},
            recommendation="Fix it",
            cwe_id="CWE-123",
            mitre_id="AI-A1001",
        )
        self.scan_result = ScanResult(
            scanner_name="backdoor",
            scanner_version="0.2.0",
            findings=[self.finding],
            metadata={"layers_analyzed": 5},
        )
        self.interpret_result = InterpretationResult(
            interpreter_name="integrated-gradients",
            interpreter_version="0.2.0",
            attributions={"feature_1": 0.5},
            summary="Mean abs attribution: 0.5",
        )

    def test_render_scan_results_markdown(self):
        output = self.generator.render_scan_results([self.scan_result], fmt="markdown")
        self.assertIn("backdoor", output)
        self.assertIn("Test Finding", output)

    def test_render_scan_results_json(self):
        output = self.generator.render_scan_results([self.scan_result], fmt="json")
        self.assertIn("backdoor", output)
        self.assertIn("Test Finding", output)
        import json
        parsed = json.loads(output)
        self.assertEqual(len(parsed), 1)

    def test_render_interpret_results_markdown(self):
        output = self.generator.render_interpret_results([self.interpret_result], fmt="markdown")
        self.assertIn("integrated-gradients", output)
        self.assertIn("0.5", output)

    def test_render_interpret_results_json(self):
        output = self.generator.render_interpret_results([self.interpret_result], fmt="json")
        self.assertIn("integrated-gradients", output)
        import json
        parsed = json.loads(output)
        self.assertEqual(len(parsed), 1)

    def test_render_interpret_results_with_error(self):
        error_result = InterpretationResult(
            interpreter_name="test-interp",
            interpreter_version="1.0",
            error="Something went wrong",
        )
        output = self.generator.render_interpret_results([error_result], fmt="markdown")
        self.assertIn("Error", output)

    def test_render_session_markdown(self):
        session = _FakeSession(
            scan_results=[self.scan_result],
            interpret_results=[self.interpret_result],
            connector_results={"splunk": "sent"},
        )
        output = self.generator.render_session(session, fmt="markdown")
        self.assertIn("test-session", output)
        self.assertIn("Test Finding", output)
        self.assertIn("splunk", output)

    def test_render_session_json(self):
        session = _FakeSession(scan_results=[self.scan_result])
        output = self.generator.render_session(session, fmt="json")
        self.assertIn("test-session", output)
        import json
        parsed = json.loads(output)
        self.assertEqual(parsed["session_id"], "test-session")
        self.assertIn("risk_score", parsed)

    def test_render_empty_session(self):
        session = _FakeSession()
        output = self.generator.render_session(session, fmt="markdown")
        self.assertIn("test-session", output)
        self.assertIn("No scanner results", output)

    def test_scanner_risk_no_findings(self):
        result = ScanResult(scanner_name="empty", scanner_version="1.0", findings=[])
        risk = self.generator._scanner_risk(result)
        self.assertEqual(risk, 0.0)

    def test_scanner_risk_with_findings(self):
        findings = [
            Finding(title="f1", description="d1", severity=Severity.CRITICAL, confidence=1.0),
            Finding(title="f2", description="d2", severity=Severity.LOW, confidence=0.5),
        ]
        result = ScanResult(scanner_name="test", scanner_version="1.0", findings=findings)
        risk = self.generator._scanner_risk(result)
        self.assertGreater(risk, 0.0)

    def test_session_risk_multiple_scanners(self):
        cr_finding = Finding(title="c", description="d", severity=Severity.CRITICAL, confidence=1.0)
        lo_finding = Finding(title="l", description="d", severity=Severity.LOW, confidence=0.2)
        r1 = ScanResult(scanner_name="s1", scanner_version="1.0", findings=[cr_finding])
        r2 = ScanResult(scanner_name="s2", scanner_version="1.0", findings=[lo_finding])
        session = _FakeSession(scan_results=[r1, r2])
        risk = self.generator._session_risk(session)
        self.assertGreater(risk, 0.0)

    def test_session_risk_no_scanners(self):
        session = _FakeSession()
        risk = self.generator._session_risk(session)
        self.assertEqual(risk, 0.0)

    def test_risk_level(self):
        self.assertEqual(self.generator._risk_level(80), "critical")
        self.assertEqual(self.generator._risk_level(60), "high")
        self.assertEqual(self.generator._risk_level(40), "medium")
        self.assertEqual(self.generator._risk_level(15), "low")
        self.assertEqual(self.generator._risk_level(5), "info")

    def test_severity_tag(self):
        self.assertIsNotNone(self.generator._severity_tag("critical"))
        self.assertIsNotNone(self.generator._severity_tag("high"))
        self.assertIsNotNone(self.generator._severity_tag("medium"))
        self.assertIsNotNone(self.generator._severity_tag("low"))
        self.assertEqual(self.generator._severity_tag("unknown"), "⚪")

    def test_truncate_text(self):
        text = "a" * 200
        truncated = self.generator._truncate_text(text, 50)
        self.assertEqual(len(truncated), 50)
        self.assertTrue(truncated.endswith("..."))

    def test_truncate_text_short(self):
        text = "short"
        truncated = self.generator._truncate_text(text, 50)
        self.assertEqual(truncated, "short")

    def test_render_markdown_with_metadata(self):
        session = _FakeSession(
            scan_results=[self.scan_result],
            metadata={"env": "production", "version": "1.0"},
        )
        output = self.generator.render_session(session, fmt="markdown")
        self.assertIn("production", output)

    def test_render_scan_results_no_findings(self):
        result = ScanResult(scanner_name="clean", scanner_version="1.0", findings=[])
        output = self.generator.render_scan_results([result], fmt="markdown")
        self.assertIn("clean", output)


class TestScanResult(unittest.TestCase):
    def test_overall_severity_empty(self):
        r = ScanResult(scanner_name="s", scanner_version="1.0")
        self.assertEqual(r.overall_severity, Severity.UNKNOWN)

    def test_overall_severity_max(self):
        findings = [
            Finding(title="a", description="d", severity=Severity.LOW, confidence=0.3),
            Finding(title="b", description="d", severity=Severity.CRITICAL, confidence=0.9),
        ]
        r = ScanResult(scanner_name="s", scanner_version="1.0", findings=findings)
        self.assertEqual(r.overall_severity, Severity.CRITICAL)

    def test_has_findings(self):
        r = ScanResult(scanner_name="s", scanner_version="1.0")
        self.assertFalse(r.has_findings)
        r.findings.append(Finding(title="t", description="d", severity=Severity.LOW, confidence=0.3))
        self.assertTrue(r.has_findings)

    def test_to_dict(self):
        r = ScanResult(scanner_name="s", scanner_version="1.0")
        r.findings.append(Finding(title="t", description="d", severity=Severity.MEDIUM, confidence=0.5))
        d = r.to_dict()
        self.assertEqual(d["scanner"], "s")
        self.assertEqual(d["finding_count"], 1)


class TestFinding(unittest.TestCase):
    def test_to_dict(self):
        f = Finding(
            title="test", description="desc", severity=Severity.HIGH, confidence=0.9,
            cwe_id="CWE-1", mitre_id="AI-1",
            evidence={"key": "val"}, recommendation="fix",
        )
        d = f.to_dict()
        self.assertEqual(d["title"], "test")
        self.assertEqual(d["cwe_id"], "CWE-1")
        self.assertEqual(d["mitre_id"], "AI-1")

    def test_to_dict_minimal(self):
        f = Finding(title="min", description="d", severity=Severity.LOW, confidence=0.5)
        d = f.to_dict()
        self.assertEqual(d["title"], "min")
        self.assertIsNone(d["cwe_id"])


class TestHTMLReporter(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.plugins.reporters.html import HTMLReporter

        self.reporter = HTMLReporter()

    def test_name_and_formats(self):
        self.assertEqual(self.reporter.name, "html")
        self.assertIn("html", self.reporter.supported_formats)

    def test_render_empty(self):
        result = self.reporter.render([], [], {
            "session_id": "test", "model_id": "m",
            "risk_score": 0, "risk_level": "info",
            "total_findings": 0,
        })
        self.assertIn("<!DOCTYPE html>", result)
        self.assertIn("test", result)

    def test_render_with_findings(self):
        from community_ai_audit.core.interfaces import ScanResult, Finding, Severity

        finding = Finding(title="XSS Vuln", description="desc", severity=Severity.HIGH, confidence=0.8)
        scan = ScanResult(scanner_name="backdoor", scanner_version="1.0", findings=[finding])
        result = self.reporter.render([scan], [], {
            "session_id": "s1", "model_id": "m1",
            "risk_score": 50, "risk_level": "medium",
            "total_findings": 1,
        })
        self.assertIn("XSS Vuln", result)
        self.assertIn("risk-badge", result)

    def test_render_with_interpretation(self):
        from community_ai_audit.core.interfaces import InterpretationResult

        interp = InterpretationResult(
            interpreter_name="ig", interpreter_version="1.0",
            summary="Feature attribution analysis",
        )
        result = self.reporter.render([], [interp], {
            "session_id": "s2", "model_id": "m2",
            "risk_score": 20, "risk_level": "low",
            "total_findings": 0,
        })
        self.assertIn("Feature attribution", result)


class TestReportGeneratorHTML(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.reporting.generator import ReportGenerator

        self.generator = ReportGenerator()

    def test_render_session_html(self):
        from community_ai_audit.core.interfaces import ScanResult, Finding, Severity

        finding = Finding(title="Test", description="d", severity=Severity.MEDIUM, confidence=0.5)
        scan = ScanResult(scanner_name="s1", scanner_version="1.0", findings=[finding])
        session = _FakeSession(scan_results=[scan])
        output = self.generator.render_session(session, fmt="html")
        self.assertIn("<!DOCTYPE html>", output)
        self.assertIn("Test", output)
        self.assertIn("risk-badge", output)


if __name__ == "__main__":
    unittest.main()
