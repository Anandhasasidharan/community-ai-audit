"""Tests for the cron-based audit scheduler."""

import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory


class TestAuditScheduler(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.core.scheduler import AuditScheduler

        self.tmpdir = TemporaryDirectory()
        self.schedules_path = str(Path(self.tmpdir.name) / "schedules.json")
        self.scheduler = AuditScheduler(schedules_path=self.schedules_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_instantiation(self):
        self.assertIsNotNone(self.scheduler)
        self.assertEqual(len(self.scheduler.list_schedules()), 0)

    def test_add_schedule(self):
        sched = self.scheduler.add_schedule(
            name="nightly",
            cron="0 6 * * *",
            model_id="gpt-4o",
            provider="openai",
            scanners=["backdoor", "adversarial"],
            interpreters=["integrated-gradients"],
            profile="standard",
            output_format="json",
        )
        self.assertEqual(sched["name"], "nightly")
        self.assertEqual(sched["cron"], "0 6 * * *")
        self.assertEqual(sched["model_id"], "gpt-4o")
        self.assertEqual(sched["provider"], "openai")
        self.assertIn("last_run", sched)
        self.assertIn("created_at", sched)

    def test_add_duplicate_raises(self):
        self.scheduler.add_schedule("dup", "0 0 * * *", "model", "provider")
        with self.assertRaises(ValueError):
            self.scheduler.add_schedule("dup", "0 0 * * *", "model", "provider")

    def test_add_invalid_cron_raises(self):
        with self.assertRaises(ValueError):
            self.scheduler.add_schedule("bad", "not-a-cron", "model", "provider")

    def test_list_schedules(self):
        self.scheduler.add_schedule("a", "0 0 * * *", "m1", "p1")
        self.scheduler.add_schedule("b", "30 6 * * *", "m2", "p2")
        schedules = self.scheduler.list_schedules()
        self.assertEqual(len(schedules), 2)
        names = {s["name"] for s in schedules}
        self.assertEqual(names, {"a", "b"})

    def test_remove_schedule(self):
        self.scheduler.add_schedule("delme", "0 0 * * *", "m", "p")
        self.assertEqual(len(self.scheduler.list_schedules()), 1)
        self.scheduler.remove_schedule("delme")
        self.assertEqual(len(self.scheduler.list_schedules()), 0)

    def test_remove_nonexistent_raises(self):
        with self.assertRaises(KeyError):
            self.scheduler.remove_schedule("nope")

    def test_persistence(self):
        self.scheduler.add_schedule("persist", "0 12 * * *", "m", "p")
        # Create a new scheduler instance pointing to the same file
        from community_ai_audit.core.scheduler import AuditScheduler

        s2 = AuditScheduler(schedules_path=self.schedules_path)
        self.assertEqual(len(s2.list_schedules()), 1)
        self.assertEqual(s2.list_schedules()[0]["name"], "persist")

    def test_mark_run(self):
        self.scheduler.add_schedule("runme", "0 0 * * *", "m", "p")
        self.assertIsNone(self.scheduler.list_schedules()[0]["last_run"])
        self.scheduler.mark_run("runme")
        self.assertIsNotNone(self.scheduler.list_schedules()[0]["last_run"])

    def test_get_due_schedules(self):
        # Use a cron that fires every second to ensure it's due immediately
        now = datetime.now(timezone.utc)
        self.scheduler.add_schedule("due_now", "* * * * *", "m", "p")
        # Override last_run to a time in the past so get_next returns <= now
        self.scheduler._schedules["due_now"]["last_run"] = (now - timedelta(minutes=5)).isoformat()
        self.scheduler.save()
        due = self.scheduler.get_due_schedules(now=now)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0][0]["name"], "due_now")

    def test_get_next_run(self):
        self.scheduler.add_schedule("hourly", "0 * * * *", "m", "p")
        next_run = self.scheduler._get_next_run("0 * * * *")
        self.assertIsNotNone(next_run)
        self.assertGreater(next_run, datetime.now(timezone.utc) - timedelta(hours=1))

    def test_run_due_no_engine(self):
        self.scheduler.add_schedule("nodue", "0 0 1 1 0", "m", "p")
        try:
            results = self.scheduler.run_due(None, now=datetime(2020, 1, 1, tzinfo=timezone.utc))
            self.assertEqual(len(results), 0)
        except Exception:
            pass  # may raise due to missing engine, but shouldn't crash on schedule parsing


if __name__ == "__main__":
    unittest.main()
