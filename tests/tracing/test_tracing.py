"""Tests for execution tracing module."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from community_ai_audit.core.tracing import (
    TraceStep,
    ExecutionTrace,
    Replayer,
    TraceExporter,
)


class TestTraceStep(unittest.TestCase):
    def test_creation(self):
        step = TraceStep(
            step=1,
            step_type="tool_call",
            input="query",
            output="result",
            duration=0.5,
        )
        self.assertEqual(step.step, 1)
        self.assertEqual(step.step_type, "tool_call")

    def test_to_dict(self):
        step = TraceStep(
            step=2,
            step_type="decision",
            input={"desc": "test"},
            output="chosen",
            duration=0.3,
        )
        d = step.to_dict()
        self.assertEqual(d["step"], 2)
        self.assertEqual(d["step_type"], "decision")

    def test_from_dict(self):
        original = TraceStep(
            step=3,
            step_type="action",
            input="input",
            output="output",
            duration=0.2,
        )
        d = original.to_dict()
        restored = TraceStep.from_dict(d)
        self.assertEqual(restored.step, 3)
        self.assertEqual(restored.step_type, "action")


class TestExecutionTrace(unittest.TestCase):
    def setUp(self):
        self.trace = ExecutionTrace(
            agent_id="test-agent",
            session_id="test-session",
        )

    def test_initialization(self):
        self.assertEqual(self.trace.agent_id, "test-agent")
        self.assertEqual(self.trace.session_id, "test-session")
        self.assertEqual(self.trace.step_count, 0)

    def test_add_step(self):
        step = TraceStep(1, "tool_call", "in", "out", 0.1)
        self.trace.add_step(step)
        self.assertEqual(self.trace.step_count, 1)

    def test_properties(self):
        self.trace.add_step(TraceStep(1, "tool_call", "in", "out", 0.1))
        self.trace.add_step(TraceStep(2, "decision", "in", "out", 0.2))
        self.trace.add_step(TraceStep(3, "action", "in", "out", 0.3))
        self.assertEqual(len(self.trace.tool_calls), 1)
        self.assertEqual(len(self.trace.decisions), 1)
        self.assertEqual(len(self.trace.actions), 1)

    def test_total_duration(self):
        self.trace.add_step(TraceStep(1, "tool_call", "in", "out", 0.5))
        self.trace.add_step(TraceStep(2, "tool_call", "in", "out", 0.3))
        self.assertAlmostEqual(self.trace.total_duration, 0.8)

    def test_finish(self):
        self.assertIsNone(self.trace.end_time)
        self.trace.finish()
        self.assertIsNotNone(self.trace.end_time)

    def test_to_dict(self):
        self.trace.add_step(TraceStep(1, "tool_call", "in", "out", 0.1))
        self.trace.finish()
        d = self.trace.to_dict()
        self.assertEqual(d["agent_id"], "test-agent")
        self.assertEqual(d["step_count"], 1)

    def test_to_json(self):
        self.trace.add_step(TraceStep(1, "tool_call", "in", "out", 0.1))
        json_str = self.trace.to_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["agent_id"], "test-agent")

    def test_from_dict(self):
        self.trace.add_step(TraceStep(1, "tool_call", "in", "out", 0.1))
        d = self.trace.to_dict()
        restored = ExecutionTrace.from_dict(d)
        self.assertEqual(restored.agent_id, "test-agent")
        self.assertEqual(restored.step_count, 1)

    def test_from_json(self):
        self.trace.add_step(TraceStep(1, "tool_call", "in", "out", 0.1))
        json_str = self.trace.to_json()
        restored = ExecutionTrace.from_json(json_str)
        self.assertEqual(restored.agent_id, "test-agent")


class TestReplayer(unittest.TestCase):
    def setUp(self):
        trace = ExecutionTrace(agent_id="test", session_id="test")
        trace.add_step(TraceStep(1, "tool_call", "in1", "out1", 0.1))
        trace.add_step(TraceStep(2, "decision", "in2", "out2", 0.2))
        trace.add_step(TraceStep(3, "action", "in3", "out3", 0.3))
        self.replayer = Replayer(trace)

    def test_total_steps(self):
        self.assertEqual(self.replayer.total_steps, 3)

    def test_next(self):
        step = self.replayer.next()
        self.assertEqual(step.step, 1)
        step = self.replayer.next()
        self.assertEqual(step.step, 2)

    def test_next_returns_none_at_end(self):
        self.replayer.next()
        self.replayer.next()
        self.replayer.next()
        self.assertIsNone(self.replayer.next())

    def test_previous(self):
        step1 = self.replayer.next()
        self.assertEqual(step1.step, 1)
        step2 = self.replayer.next()
        self.assertEqual(step2.step, 2)
        prev = self.replayer.previous()
        self.assertEqual(prev.step, 2)

    def test_reset(self):
        self.replayer.next()
        self.replayer.reset()
        self.assertEqual(self.replayer.progress, 0.0)
        step = self.replayer.next()
        self.assertEqual(step.step, 1)

    def test_seek(self):
        step = self.replayer.seek(3)
        self.assertEqual(step.step, 3)
        self.assertAlmostEqual(self.replayer.progress, 2.0 / 3.0)

    def test_seek_not_found(self):
        step = self.replayer.seek(99)
        self.assertIsNone(step)

    def test_progress(self):
        self.assertAlmostEqual(self.replayer.progress, 0.0)
        self.replayer.next()
        self.assertAlmostEqual(self.replayer.progress, 1.0 / 3.0)

    def test_summary(self):
        summary = self.replayer.summary()
        self.assertEqual(summary["total_steps"], 3)
        self.assertEqual(summary["tool_calls"], 1)

    def test_stats(self):
        stats = self.replayer.stats()
        self.assertAlmostEqual(stats["min_step_duration"], 0.1)
        self.assertAlmostEqual(stats["max_step_duration"], 0.3)
        self.assertAlmostEqual(stats["avg_step_duration"], 0.2)

    def test_replay_all(self):
        captured = []
        self.replayer.replay_all(step_callback=captured.append)
        self.assertEqual(len(captured), 3)

    def test_replay_all_with_filter(self):
        captured = []
        self.replayer.replay_all(
            step_callback=captured.append,
            step_filter=lambda s: s.step_type == "tool_call",
        )
        self.assertEqual(len(captured), 1)


class TestTraceExporter(unittest.TestCase):
    def setUp(self):
        trace = ExecutionTrace(agent_id="test", session_id="test")
        trace.add_step(TraceStep(1, "tool_call", "in", "out", 0.1))
        trace.add_step(TraceStep(2, "decision", "in2", "out2", 0.2))
        self.exporter = TraceExporter(trace)

    def test_to_json(self):
        result = self.exporter.to_json()
        parsed = json.loads(result)
        self.assertEqual(parsed["agent_id"], "test")

    def test_to_jsonl(self):
        result = self.exporter.to_jsonl()
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 2)

    def test_to_html(self):
        html = self.exporter.to_html()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("test", html)

    def test_to_markdown(self):
        md = self.exporter.to_markdown()
        self.assertIn("Execution Trace", md)
        self.assertIn("| Step |", md)

    def test_save_json(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            self.exporter.save(path)
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["agent_id"], "test")
        finally:
            os.unlink(path)

    def test_save_html(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            path = f.name
        try:
            self.exporter.save(path)
            with open(path) as f:
                content = f.read()
            self.assertIn("<!DOCTYPE html>", content)
        finally:
            os.unlink(path)

    def test_save_auto_format(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            self.exporter.save(path)
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["agent_id"], "test")
        finally:
            os.unlink(path)
