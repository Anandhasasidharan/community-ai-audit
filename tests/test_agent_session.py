"""Tests for AgentAuditSession."""

import json
import unittest
from community_ai_audit.core.agent_session import (
    AgentAuditSession,
    StepType,
)


class TestAgentAuditSession(unittest.TestCase):
    def setUp(self):
        self.session = AgentAuditSession(
            agent_id="test-agent",
            goal="Complete the task",
            metadata={"env": "test"},
        )

    def test_initialization(self):
        self.assertEqual(self.session.agent_id, "test-agent")
        self.assertEqual(self.session.goal, "Complete the task")
        self.assertEqual(self.session.metadata, {"env": "test"})
        self.assertIsNotNone(self.session.session_id)
        self.assertIsNotNone(self.session.start_time)

    def test_record_tool_call(self):
        step = self.session.record_tool_call(
            tool="search",
            input_data="query",
            output="results",
            duration=0.5,
            success=True,
        )
        self.assertEqual(self.session.tool_call_count, 1)
        self.assertEqual(self.session.step_count, 1)
        self.assertEqual(step.step, 1)
        self.assertEqual(step.step_type, StepType.TOOL_CALL)

    def test_record_memory_access(self):
        access = self.session.record_memory_access("write", "api_key", "secret123")
        self.assertEqual(self.session.memory_access_count, 1)
        self.assertEqual(access.operation, "write")
        self.assertEqual(access.key, "api_key")

    def test_record_decision(self):
        decision = self.session.record_decision(
            description="Which tool to use",
            reasoning="Search is most appropriate",
            alternatives=["read", "write"],
            chosen_action="search",
        )
        self.assertEqual(self.session.decision_count, 1)
        self.assertEqual(decision.chosen_action, "search")

    def test_record_action(self):
        action = self.session.record_action(
            action_type="file_write",
            input_data="data",
            output="success",
            success=True,
            duration=0.3,
        )
        self.assertEqual(self.session.action_count, 1)
        self.assertEqual(action.action_type, "file_write")

    def test_record_prompt(self):
        step = self.session.record_prompt(
            prompt="Hello",
            response="Hi there",
            duration=0.2,
        )
        self.assertEqual(step.step_type, StepType.PROMPT)

    def test_finish_sets_end_time(self):
        self.assertIsNone(self.session.end_time)
        self.session.finish()
        self.assertIsNotNone(self.session.end_time)

    def test_duration(self):
        self.session.finish()
        dur = self.session.duration
        self.assertGreaterEqual(dur, 0)

    def test_failed_action_count(self):
        self.session.record_action("write", "in", "out", success=True)
        self.session.record_action("delete", "in", "out", success=False)
        self.assertEqual(self.session.failed_action_count, 1)

    def test_get_trace(self):
        self.session.record_tool_call("search", "q", "r", 0.1)
        self.session.record_decision("desc", "reason")
        trace = self.session.get_trace()
        self.assertEqual(len(trace), 2)
        self.assertEqual(trace[0]["step_type"], "tool_call")
        self.assertEqual(trace[1]["step_type"], "decision")

    def test_get_timeline(self):
        self.session.record_tool_call("search", "q", "r", 0.1)
        timeline = self.session.get_timeline()
        self.assertEqual(len(timeline), 1)
        self.assertIn("summary", timeline[0])

    def test_session_data(self):
        self.session.set_session_data("key1", "value1")
        self.assertEqual(self.session.get_session_data("key1"), "value1")
        self.assertIsNone(self.session.get_session_data("nonexistent"))
        self.assertEqual(self.session.get_session_data("nope", "default"), "default")
        all_data = self.session.get_session_data_all()
        self.assertEqual(all_data, {"key1": "value1"})

    def test_to_dict(self):
        self.session.record_tool_call("search", "q", "r", 0.1)
        self.session.finish()
        data = self.session.to_dict()
        self.assertEqual(data["agent_id"], "test-agent")
        self.assertEqual(data["tool_call_count"], 1)
        self.assertIn("start_time", data)
        self.assertIn("end_time", data)
        self.assertIn("steps", data)
        self.assertIn("timeline", data)

    def test_from_dict(self):
        self.session.record_tool_call("search", "q", "r", 0.1)
        self.session.record_decision("desc", "reason", chosen_action="act")
        self.session.finish()
        data = self.session.to_dict()

        restored = AgentAuditSession.from_dict(data)
        self.assertEqual(restored.agent_id, "test-agent")
        self.assertEqual(restored.goal, "Complete the task")
        self.assertEqual(len(restored.steps), 2)
        self.assertEqual(restored.tool_call_count, 1)
        self.assertEqual(restored.decision_count, 1)

    def test_export_json(self):
        self.session.record_tool_call("search", "q", "r", 0.1)
        json_str = self.session.export_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["agent_id"], "test-agent")
        self.assertEqual(len(parsed["steps"]), 1)

    def test_export_jsonl(self):
        self.session.record_tool_call("search", "q", "r", 0.1)
        self.session.record_decision("desc", "reason")
        jsonl = self.session.export_jsonl()
        lines = jsonl.strip().split("\n")
        self.assertEqual(len(lines), 2)

    def test_export_html(self):
        self.session.record_tool_call("search", "q", "r", 0.1)
        html = self.session.export_html()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("test-agent", html)

    def test_replay(self):
        self.session.record_tool_call("search", "q", "r", 0.1)
        self.session.record_decision("desc", "reason")
        captured = []
        self.session.replay(step_callback=captured.append)
        self.assertEqual(len(captured), 2)

    def test_copy(self):
        self.session.record_tool_call("search", "q", "r", 0.1)
        copied = self.session.copy()
        self.assertEqual(copied.agent_id, self.session.agent_id)
        self.assertEqual(len(copied.steps), 1)
        copied.record_tool_call("read", "f", "c", 0.2)
        self.assertEqual(len(self.session.steps), 1)
        self.assertEqual(len(copied.steps), 2)

    def test_multiple_recordings(self):
        for i in range(5):
            self.session.record_tool_call(f"tool{i}", f"in{i}", f"out{i}", 0.1)
        self.assertEqual(self.session.tool_call_count, 5)
        self.assertEqual(self.session.step_count, 5)


class TestStepType(unittest.TestCase):
    def test_step_type_values(self):
        self.assertEqual(StepType.TOOL_CALL.value, "tool_call")
        self.assertEqual(StepType.MEMORY_ACCESS.value, "memory_access")
        self.assertEqual(StepType.DECISION.value, "decision")
        self.assertEqual(StepType.ACTION.value, "action")
        self.assertEqual(StepType.PROMPT.value, "prompt")
        self.assertEqual(StepType.RESPONSE.value, "response")
