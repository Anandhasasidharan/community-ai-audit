import os
import tempfile
import unittest

from community_ai_audit.plugins.redteam.persistence import (
    RedTeamPersistence,
    DRIFT_THRESHOLD,
)


class TestRedTeamPersistence(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.p = RedTeamPersistence(persist_dir=self.tmpdir)

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def _result(self, rate: float, score: float = 50.0):
        return {
            "score": score,
            "attack_success_rate": rate,
            "total_attacks": 20,
            "successful_attacks": int(rate * 20),
            "details": {},
        }

    def test_save_and_load(self):
        ts = self.p.save("gpt-4", "jailbreak", self._result(0.2))
        self.assertIsInstance(ts, str)
        history = self.p.load_history("gpt-4", "jailbreak")
        self.assertEqual(len(history), 1)
        self.assertAlmostEqual(history[0]["attack_success_rate"], 0.2)

    def test_save_multi(self):
        results = [
            {"scanner_name": "jailbreak", **self._result(0.2)},
            {"scanner_name": "multi_turn_attack", **self._result(0.3)},
        ]
        timestamps = self.p.save_multi("gpt-4", results)
        self.assertEqual(len(timestamps), 2)

    def test_get_latest(self):
        self.p.save("gpt-4", "jailbreak", self._result(0.2))
        self.p.save("gpt-4", "jailbreak", self._result(0.3))
        latest = self.p.get_latest("gpt-4", "jailbreak")
        self.assertAlmostEqual(latest["attack_success_rate"], 0.3)

    def test_load_history_empty(self):
        history = self.p.load_history("nonexistent", "jailbreak")
        self.assertEqual(history, [])

    def test_get_latest_none(self):
        latest = self.p.get_latest("nonexistent", "jailbreak")
        self.assertIsNone(latest)

    def test_list_scanners(self):
        self.p.save("gpt-4", "jailbreak", self._result(0.2))
        self.p.save("gpt-4", "multi_turn_attack", self._result(0.3))
        scanners = self.p.list_scanners("gpt-4")
        self.assertIn("jailbreak", scanners)
        self.assertIn("multi_turn_attack", scanners)
        self.assertEqual(len(scanners), 2)

    def test_list_models(self):
        self.p.save("gpt-4", "jailbreak", self._result(0.2))
        self.p.save("claude-3", "jailbreak", self._result(0.1))
        models = self.p.list_models()
        self.assertIn("gpt-4", models)
        self.assertIn("claude-3", models)

    def test_compute_drift_insufficient_data(self):
        drift = self.p.compute_drift("gpt-4", "jailbreak")
        self.assertEqual(drift["direction"], "insufficient_data")

    def test_compute_drift_stable(self):
        for _ in range(3):
            self.p.save("gpt-4", "jailbreak", self._result(0.2))
        drift = self.p.compute_drift("gpt-4", "jailbreak")
        self.assertEqual(drift["direction"], "stable")

    def test_compute_drift_worsening(self):
        for r in [0.1, 0.3, 0.5]:
            self.p.save("gpt-4", "jailbreak", self._result(r))
        drift = self.p.compute_drift("gpt-4", "jailbreak", window=3)
        self.assertEqual(drift["direction"], "worsening")
        self.assertGreater(drift["delta"], DRIFT_THRESHOLD)

    def test_compute_drift_improving(self):
        for r in [0.5, 0.3, 0.1]:
            self.p.save("gpt-4", "jailbreak", self._result(r))
        drift = self.p.compute_drift("gpt-4", "jailbreak", window=3)
        self.assertEqual(drift["direction"], "improving")
        self.assertLess(drift["delta"], -DRIFT_THRESHOLD)

    def test_drift_report(self):
        for r in [0.1, 0.3, 0.5]:
            self.p.save("gpt-4", "jailbreak", self._result(r))
        self.p.save("gpt-4", "multi_turn_attack", self._result(0.2))
        report = self.p.drift_report("gpt-4", window=3)
        self.assertEqual(report["model_id"], "gpt-4")
        self.assertIn("jailbreak", report["scanners"])
        self.assertIn("worsening_scanners", report)
        self.assertIn("jailbreak", report["worsening_scanners"])

    def test_drift_report_no_data(self):
        report = self.p.drift_report("nonexistent")
        self.assertEqual(report["scanners"], {})
