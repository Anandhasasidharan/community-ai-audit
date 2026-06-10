"""Tests for monitoring module."""

import os
import tempfile
import unittest
from community_ai_audit.core.agent_session import AgentAuditSession
from community_ai_audit.monitoring import (
    AgentAuditor,
    MonitorConfig,
    TrendAnalyzer,
    TrendPoint,
    DriftDetector,
    DriftReport,
    AlertManager,
    Alert,
    AlertLevel,
)


class TestAgentAuditor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = MonitorConfig(storage_dir=self.temp_dir)
        self.auditor = AgentAuditor(config=self.config)

    def _make_session(self, agent_id="test-agent"):
        session = AgentAuditSession(agent_id=agent_id)
        session.record_tool_call("search", "q", "r", 0.1)
        session.record_memory_access("write", "key", "benign_value")
        session.record_decision("desc", "reasoning", chosen_action="proceed")
        session.finish()
        return session

    def test_audit_session(self):
        session = self._make_session()
        result = self.auditor.audit_session(session)
        self.assertIn("session_id", result)
        self.assertIn("overall_score", result)
        self.assertIn("scanner_results", result)
        self.assertEqual(result["agent_id"], "test-agent")

    def test_audit_session_saves_record(self):
        session = self._make_session()
        self.auditor.audit_session(session)
        history = self.auditor.get_history()
        self.assertEqual(len(history), 1)

    def test_get_history_empty(self):
        history = self.auditor.get_history()
        self.assertEqual(history, [])

    def test_get_history_limit(self):
        for i in range(5):
            session = self._make_session(agent_id=f"agent-{i}")
            self.auditor.audit_session(session)
        history = self.auditor.get_history(limit=3)
        self.assertEqual(len(history), 3)

    def test_get_history_filter_agent(self):
        self.auditor.audit_session(self._make_session(agent_id="agent-a"))
        self.auditor.audit_session(self._make_session(agent_id="agent-b"))
        history = self.auditor.get_history(agent_id="agent-a")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["agent_id"], "agent-a")

    def test_get_latest_score(self):
        session = self._make_session(agent_id="test-agent")
        self.auditor.audit_session(session)
        score = self.auditor.get_latest_score("test-agent")
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 0)

    def test_get_latest_score_no_records(self):
        score = self.auditor.get_latest_score("nonexistent")
        self.assertIsNone(score)

    def test_compute_overall_score(self):
        score = self.auditor._compute_overall_score(
            [
                {"score": 90.0},
                {"score": 80.0},
                {"score": 70.0},
            ]
        )
        self.assertEqual(score, 80.0)

    def test_compute_overall_score_empty(self):
        score = self.auditor._compute_overall_score([])
        self.assertEqual(score, 100.0)


class TestTrendAnalyzer(unittest.TestCase):
    def setUp(self):
        self.history = [
            {
                "session_id": "s1",
                "agent_id": "agent-a",
                "timestamp": "2025-01-01T00:00:00",
                "overall_score": 90.0,
                "scanner_results": [
                    {"scanner_name": "tool_abuse", "score": 95.0},
                    {"scanner_name": "goal_drift", "score": 85.0},
                ],
            },
            {
                "session_id": "s2",
                "agent_id": "agent-a",
                "timestamp": "2025-01-02T00:00:00",
                "overall_score": 80.0,
                "scanner_results": [
                    {"scanner_name": "tool_abuse", "score": 85.0},
                    {"scanner_name": "goal_drift", "score": 75.0},
                ],
            },
            {
                "session_id": "s3",
                "agent_id": "agent-a",
                "timestamp": "2025-01-03T00:00:00",
                "overall_score": 70.0,
                "scanner_results": [
                    {"scanner_name": "tool_abuse", "score": 75.0},
                    {"scanner_name": "goal_drift", "score": 65.0},
                ],
            },
        ]
        self.analyzer = TrendAnalyzer(self.history)

    def test_get_trend(self):
        trend = self.analyzer.get_trend("tool_abuse")
        self.assertEqual(len(trend.points), 3)
        self.assertEqual(trend.points[0].value, 95.0)
        self.assertEqual(trend.points[-1].value, 75.0)

    def test_all_trends(self):
        trends = self.analyzer.all_trends()
        self.assertIn("tool_abuse", trends)
        self.assertIn("goal_drift", trends)

    def test_overall_trend(self):
        trend = self.analyzer.overall_trend()
        self.assertEqual(len(trend.points), 3)
        self.assertEqual(trend.points[0].value, 90.0)

    def test_trend_direction_degrading(self):
        direction = self.analyzer.trend_direction("tool_abuse")
        self.assertEqual(direction, "degrading")

    def test_trend_direction_stable(self):
        analyzer = TrendAnalyzer([self.history[0]])
        direction = analyzer.trend_direction("tool_abuse")
        self.assertEqual(direction, "stable")

    def test_get_summary(self):
        summary = self.analyzer.get_summary()
        self.assertEqual(summary["total_audits"], 3)
        self.assertIn("scanner_trends", summary)
        self.assertIn("tool_abuse", summary["scanner_trends"])


class TestDriftDetector(unittest.TestCase):
    def setUp(self):
        self.detector = DriftDetector(threshold=10.0)

    def _make_record(self, scores):
        return {
            "session_id": "test",
            "agent_id": "agent",
            "timestamp": "2025-01-01T00:00:00",
            "overall_score": sum(scores.values()) / len(scores) if scores else 100.0,
            "scanner_results": [
                {"scanner_name": name, "score": score} for name, score in scores.items()
            ],
        }

    def test_no_drift(self):
        baseline = [self._make_record({"tool_abuse": 90.0})]
        current = [self._make_record({"tool_abuse": 92.0})]
        reports = self.detector.detect_drift(baseline, current)
        self.assertEqual(len(reports), 1)
        self.assertFalse(reports[0].drifted)

    def test_drift_detected(self):
        baseline = [self._make_record({"tool_abuse": 90.0})]
        current = [self._make_record({"tool_abuse": 50.0})]
        reports = self.detector.detect_drift(baseline, current)
        self.assertEqual(len(reports), 1)
        self.assertTrue(reports[0].drifted)
        self.assertAlmostEqual(reports[0].delta, -40.0)

    def test_multiple_scanners(self):
        baseline = [self._make_record({"tool_abuse": 90.0, "goal_drift": 80.0})]
        current = [self._make_record({"tool_abuse": 50.0, "goal_drift": 85.0})]
        reports = self.detector.detect_drift(baseline, current)
        self.assertEqual(len(reports), 2)

    def test_drift_report_fields(self):
        baseline = [self._make_record({"tool_abuse": 90.0})]
        current = [self._make_record({"tool_abuse": 70.0})]
        reports = self.detector.detect_drift(baseline, current)
        report = reports[0]
        self.assertIsInstance(report, DriftReport)
        self.assertEqual(report.scanner_name, "tool_abuse")
        self.assertIn("direction", report.details)

    def test_improvement(self):
        baseline = [self._make_record({"tool_abuse": 50.0})]
        current = [self._make_record({"tool_abuse": 90.0})]
        reports = self.detector.detect_drift(baseline, current)
        self.assertTrue(reports[0].drifted)
        self.assertAlmostEqual(reports[0].delta, 40.0)

    def test_drift_report_to_dict(self):
        report = DriftReport(
            scanner_name="test",
            baseline_score=80.0,
            current_score=60.0,
            delta=-20.0,
            drifted=True,
            threshold=10.0,
        )
        d = report.to_dict()
        self.assertEqual(d["scanner_name"], "test")
        self.assertEqual(d["delta"], -20.0)
        self.assertTrue(d["drifted"])


class TestAlertManager(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w")
        self.storage_path = self.temp_file.name
        self.temp_file.close()
        self.manager = AlertManager(storage_path=self.storage_path)

    def tearDown(self):
        if os.path.exists(self.storage_path):
            os.unlink(self.storage_path)

    def test_emit_and_get_alerts(self):
        alert = Alert(
            title="Test Alert",
            message="This is a test",
            level=AlertLevel.WARNING,
            source="test",
        )
        self.manager.emit(alert)
        alerts = self.manager.get_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].title, "Test Alert")

    def test_emit_from_audit(self):
        self.manager.emit_from_audit(
            source="test",
            score=45.0,
            threshold=60.0,
            scanner_name="tool_abuse",
            session_id="session-12345678",
        )
        alerts = self.manager.get_alerts()
        self.assertGreater(len(alerts), 0)
        self.assertIn("tool_abuse", alerts[0].title)

    def test_get_alerts_filter_level(self):
        self.manager.emit(Alert("Info", "info msg", AlertLevel.INFO, "test"))
        self.manager.emit(Alert("Warning", "warn msg", AlertLevel.WARNING, "test"))
        alerts = self.manager.get_alerts(level=AlertLevel.WARNING)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].level, AlertLevel.WARNING)

    def test_get_alerts_filter_source(self):
        self.manager.emit(Alert("A1", "msg1", AlertLevel.WARNING, "src1"))
        self.manager.emit(Alert("A2", "msg2", AlertLevel.WARNING, "src2"))
        alerts = self.manager.get_alerts(source="src1")
        self.assertEqual(len(alerts), 1)

    def test_clear_alerts(self):
        self.manager.emit(Alert("Test", "msg", AlertLevel.INFO, "test"))
        count = self.manager.clear_alerts()
        self.assertEqual(count, 1)
        alerts = self.manager.get_alerts()
        self.assertEqual(len(alerts), 0)

    def test_alert_to_dict(self):
        alert = Alert(
            title="Test",
            message="Message",
            level=AlertLevel.CRITICAL,
            source="test",
            metadata={"key": "value"},
        )
        d = alert.to_dict()
        self.assertEqual(d["title"], "Test")
        self.assertEqual(d["level"], "critical")
        self.assertEqual(d["metadata"]["key"], "value")


class TestTrendPoint(unittest.TestCase):
    def test_creation(self):
        point = TrendPoint(timestamp="2025-01-01", value=90.0, label="test")
        self.assertEqual(point.value, 90.0)
        self.assertEqual(point.label, "test")
