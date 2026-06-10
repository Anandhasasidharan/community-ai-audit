import json
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from community_ai_audit.core.evaluation.trends import (
    AuditTrendTracker,
    TrendSnapshot,
    TrendResult,
)


class TestTrendSnapshot(unittest.TestCase):
    def test_to_dict(self):
        ts = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
        snap = TrendSnapshot(
            model_id="gpt-4",
            timestamp=ts,
            scores={"security": 85.0, "alignment": 72.0},
            metadata={"provider": "openai"},
            snapshot_id="test-123",
        )
        d = snap.to_dict()
        self.assertEqual(d["model_id"], "gpt-4")
        self.assertEqual(d["snapshot_id"], "test-123")
        self.assertIn("security", d["scores"])

    def test_from_dict(self):
        data = {
            "model_id": "claude-3",
            "timestamp": "2026-06-10T12:00:00+00:00",
            "scores": {"reliability": 90.0, "interpretability": 65.0},
            "metadata": {},
            "snapshot_id": "snap-456",
        }
        snap = TrendSnapshot.from_dict(data)
        self.assertEqual(snap.model_id, "claude-3")
        self.assertEqual(snap.snapshot_id, "snap-456")
        self.assertAlmostEqual(snap.scores["reliability"], 90.0)


class TestTrendResult(unittest.TestCase):
    def test_is_degrading(self):
        r = TrendResult(
            dimension="security",
            direction="degrading",
            magnitude=-10.0,
            slope=-5.0,
            current=70.0,
            previous=80.0,
            window=3,
        )
        self.assertTrue(r.is_degrading)
        self.assertFalse(r.is_improving)
        self.assertFalse(r.is_stable)

    def test_is_improving(self):
        r = TrendResult(
            dimension="alignment",
            direction="improving",
            magnitude=8.0,
            slope=4.0,
            current=88.0,
            previous=80.0,
            window=3,
        )
        self.assertTrue(r.is_improving)

    def test_is_stable(self):
        r = TrendResult(
            dimension="compliance",
            direction="stable",
            magnitude=2.0,
            slope=1.0,
            current=82.0,
            previous=81.0,
            window=3,
        )
        self.assertTrue(r.is_stable)

    def test_summary(self):
        r = TrendResult(
            dimension="red_team",
            direction="degrading",
            magnitude=-8.0,
            slope=-4.0,
            current=60.0,
            previous=68.0,
            window=3,
        )
        s = r.summary()
        self.assertIn("red_team", s)
        self.assertIn("degrading", s)


class TestAuditTrendTracker(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tracker = AuditTrendTracker(storage_dir=self.tmpdir)

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_record_and_get_latest(self):
        sid = self.tracker.record("gpt-4", {"security": 85.0, "alignment": 72.0})
        self.assertIn("gpt-4", sid)
        latest = self.tracker.get_latest("gpt-4")
        self.assertIsNotNone(latest)
        self.assertAlmostEqual(latest.scores["security"], 85.0)

    def test_record_with_metadata(self):
        self.tracker.record(
            "claude-3",
            {"reliability": 92.0},
            metadata={"provider": "anthropic", "version": "claude-3-opus"},
        )
        latest = self.tracker.get_latest("claude-3")
        self.assertEqual(latest.metadata["provider"], "anthropic")

    def test_get_history_empty(self):
        history = self.tracker.get_history("nonexistent")
        self.assertEqual(history, [])

    def test_get_history_ordered(self):
        now = datetime.now(timezone.utc)
        for i in range(5):
            snap = TrendSnapshot(
                model_id="gpt-4",
                timestamp=now - timedelta(hours=i),
                scores={"security": float(80 + i)},
                snapshot_id=f"snap-{i}",
            )
            self._write_snapshot_direct(snap)
        history = self.tracker.get_history("gpt-4", limit=3)
        self.assertEqual(len(history), 3)

    def _write_snapshot_direct(self, snap):
        path = self.tracker._model_path(snap.model_id)
        with open(path, "a") as f:
            f.write(json.dumps(snap.to_dict()) + "\n")

    def test_list_models(self):
        self.tracker.record("gpt-4", {"security": 80.0})
        self.tracker.record("claude-3", {"security": 85.0})
        models = self.tracker.list_models()
        self.assertIn("gpt-4", models)
        self.assertIn("claude-3", models)

    def test_compute_trend_insufficient_data(self):
        r = self.tracker.compute_trend("gpt-4", "security", window=3)
        self.assertEqual(r.direction, "insufficient_data")

    def test_compute_trend_stable(self):
        for i in range(3):
            snap = TrendSnapshot(
                model_id="gpt-4",
                timestamp=datetime.now(timezone.utc) - timedelta(hours=i),
                scores={"security": 80.0},
                snapshot_id=f"snap-{i}",
            )
            self._write_snapshot_direct(snap)
        r = self.tracker.compute_trend("gpt-4", "security", window=3)
        self.assertEqual(r.direction, "stable")

    def test_compute_trend_improving(self):
        for i in range(3):
            snap = TrendSnapshot(
                model_id="gpt-4",
                timestamp=datetime.now(timezone.utc) - timedelta(hours=2 - i),
                scores={"security": float(70 + i * 5)},
                snapshot_id=f"snap-{i}",
            )
            self._write_snapshot_direct(snap)
        r = self.tracker.compute_trend("gpt-4", "security", window=3)
        self.assertEqual(r.direction, "improving")
        self.assertGreater(r.magnitude, 0)

    def test_compute_trend_degrading(self):
        for i in range(3):
            snap = TrendSnapshot(
                model_id="gpt-4",
                timestamp=datetime.now(timezone.utc) - timedelta(hours=2 - i),
                scores={"security": float(90 - i * 8)},
                snapshot_id=f"snap-{i}",
            )
            self._write_snapshot_direct(snap)
        r = self.tracker.compute_trend("gpt-4", "security", window=3)
        self.assertEqual(r.direction, "degrading")
        self.assertLess(r.magnitude, 0)

    def test_trend_report_all_dimensions(self):
        for i in range(3):
            snap = TrendSnapshot(
                model_id="gpt-4",
                timestamp=datetime.now(timezone.utc) - timedelta(hours=i),
                scores={
                    "security": 80.0,
                    "reliability": 85.0,
                    "compliance": 90.0,
                    "agent_risk": 75.0,
                    "alignment": 82.0,
                    "red_team": 70.0,
                    "interpretability": 65.0,
                },
                snapshot_id=f"snap-{i}",
            )
            self._write_snapshot_direct(snap)
        report = self.tracker.trend_report("gpt-4", window=3)
        self.assertEqual(len(report), 7)
        for dim, r in report.items():
            self.assertIn(r.direction, {"stable", "improving", "degrading"})

    def test_cleanup(self):
        for i in range(10):
            snap = TrendSnapshot(
                model_id="gpt-4",
                timestamp=datetime.now(timezone.utc) - timedelta(hours=i),
                scores={"security": 80.0},
                snapshot_id=f"snap-{i}",
            )
            self._write_snapshot_direct(snap)
        self.tracker.cleanup(max_snapshots=3)
        history = self.tracker.get_history("gpt-4", limit=100)
        self.assertLessEqual(len(history), 3)

    def test_get_history_with_dimension_filter(self):
        snap1 = TrendSnapshot(
            model_id="gpt-4",
            scores={"security": 80.0, "alignment": 70.0},
            snapshot_id="snap-1",
        )
        snap2 = TrendSnapshot(
            model_id="gpt-4",
            scores={"security": 85.0},
            snapshot_id="snap-2",
        )
        self._write_snapshot_direct(snap1)
        self._write_snapshot_direct(snap2)
        history = self.tracker.get_history("gpt-4", dimension="alignment", limit=10)
        self.assertEqual(len(history), 1)
        self.assertIn("alignment", history[0].scores)
