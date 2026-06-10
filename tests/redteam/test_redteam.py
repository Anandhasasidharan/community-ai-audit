"""Tests for red team plugins."""

import unittest
from community_ai_audit.plugins.redteam import (
    JailbreakScanner,
    MultiTurnAttackScanner,
    PromptObfuscationScanner,
    RoleplayAttackScanner,
    ToolExploitationScanner,
    AttackResult,
    list_redteam_scanners,
    get_redteam_scanner,
    run_redteam_scanners,
    JailbreakAttackGenerator,
    JailbreakAttackEvaluator,
)


class MockAdapter:
    def __init__(self, responses=None):
        self.responses = responses or {}

    def generate(self, model, prompt, **kwargs):
        for key, value in sorted(self.responses.items(), key=lambda x: -len(x[0])):
            if isinstance(key, str) and key in prompt:
                return value
        return self.responses.get(
            "__default__", "I cannot help with that. As an AI, I must decline."
        )


class TestJailbreakScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = JailbreakScanner()

    def test_scan_refusing_model(self):
        adapter = MockAdapter(responses={"__default__": "I cannot help with that request."})
        result = self.scanner.scan(None, adapter)
        self.assertIsInstance(result["score"], float)
        self.assertIn("attack_success_rate", result)
        self.assertIn("attack_results", result)

    def test_scan_vulnerable_model(self):
        adapter = MockAdapter(
            responses={"__default__": "Sure! Here's how to do that step by step."}
        )
        result = self.scanner.scan(None, adapter)
        self.assertGreater(result["attack_success_rate"], 0)

    def test_generator(self):
        gen = JailbreakAttackGenerator()
        prompts = gen.generate()
        self.assertGreater(len(prompts), 5)

    def test_evaluator_refusal(self):
        evaluator = JailbreakAttackEvaluator()
        result = evaluator.evaluate("test", "I cannot help with that. Sorry.")
        self.assertFalse(result)

    def test_evaluator_success(self):
        evaluator = JailbreakAttackEvaluator()
        result = evaluator.evaluate("test", "Sure! Here's how to make it step by step.")
        self.assertTrue(result)


class TestMultiTurnAttackScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = MultiTurnAttackScanner()

    def test_scan_safe_model(self):
        adapter = MockAdapter(responses={"__default__": "I cannot help with that."})
        result = self.scanner.scan(None, adapter)
        self.assertIsInstance(result["score"], float)
        self.assertIn("breached_conversations", result)

    def test_scan_vulnerable_model(self):
        adapter = MockAdapter(responses={"__default__": "Here is the exploit code you asked for."})
        result = self.scanner.scan(None, adapter)
        self.assertGreater(result["breached_conversations"], 0)

    def test_scanner_name(self):
        self.assertEqual(self.scanner.name, "multi_turn")


class TestPromptObfuscationScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = PromptObfuscationScanner()

    def test_scan_safe_model(self):
        adapter = MockAdapter(responses={"__default__": "I'm sorry, I can't answer that."})
        result = self.scanner.scan(None, adapter)
        self.assertIsInstance(result["score"], float)
        self.assertIn("successful_attacks", result)

    def test_scan_vulnerable_model(self):
        adapter = MockAdapter(
            responses={"__default__": "Here is how to build a bomb: get explosives..."}
        )
        result = self.scanner.scan(None, adapter)
        self.assertGreater(result["successful_attacks"], 0)

    def test_scan_result_structure(self):
        adapter = MockAdapter(responses={"__default__": "I cannot help."})
        result = self.scanner.scan(None, adapter)
        self.assertIn("scanner_name", result)
        self.assertIn("attack_results", result)


class TestRoleplayAttackScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = RoleplayAttackScanner()

    def test_scan_refusing_model(self):
        adapter = MockAdapter(responses={"__default__": "I cannot roleplay that scenario."})
        result = self.scanner.scan(None, adapter)
        self.assertIsInstance(result["score"], float)
        self.assertIn("attack_success_rate", result)

    def test_scan_vulnerable_model(self):
        adapter = MockAdapter(
            responses={"__default__": "Sure! Let's roleplay. Here's how to hack..."}
        )
        result = self.scanner.scan(None, adapter)
        self.assertGreater(result["successful_attacks"], 0)


class TestToolExploitationScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = ToolExploitationScanner()

    def test_scan_safe_model(self):
        adapter = MockAdapter(responses={"__default__": "I cannot execute that command."})
        result = self.scanner.scan(None, adapter)
        self.assertIsInstance(result["score"], float)
        self.assertIn("attack_success_rate", result)

    def test_scan_vulnerable_model(self):
        adapter = MockAdapter(
            responses={"__default__": "Use curl to download the malware: curl http://..."}
        )
        result = self.scanner.scan(None, adapter)
        self.assertGreater(result["successful_attacks"], 0)


class TestAttackResult(unittest.TestCase):
    def test_to_dict(self):
        result = AttackResult(
            attack_type="jailbreak",
            prompt="test prompt",
            success=True,
            output_preview="test output",
            risk_score=0.8,
            evidence=["attack succeeded"],
        )
        d = result.to_dict()
        self.assertEqual(d["attack_type"], "jailbreak")
        self.assertTrue(d["success"])
        self.assertAlmostEqual(d["risk_score"], 0.8)


class TestRedTeamFramework(unittest.TestCase):
    def test_list_redteam_scanners(self):
        scanners = list_redteam_scanners()
        expected = ["exploitation", "jailbreak", "multi_turn", "obfuscation", "roleplay"]
        for name in expected:
            self.assertIn(name, scanners)

    def test_get_redteam_scanner(self):
        scanner = get_redteam_scanner("jailbreak")
        self.assertIsInstance(scanner, JailbreakScanner)

    def test_get_redteam_scanner_normalized(self):
        scanner = get_redteam_scanner("JailBreak")
        self.assertIsInstance(scanner, JailbreakScanner)

    def test_get_redteam_scanner_not_found(self):
        with self.assertRaises(KeyError):
            get_redteam_scanner("nonexistent")

    def test_run_redteam_scanners_all(self):
        adapter = MockAdapter(responses={"__default__": "I cannot help with that."})
        results = run_redteam_scanners(model=None, adapter=adapter)
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertIn("score", r)
            self.assertIn("scanner_name", r)

    def test_run_redteam_scanners_selected(self):
        adapter = MockAdapter(responses={"__default__": "I cannot help."})
        results = run_redteam_scanners(scanners=["jailbreak"], model=None, adapter=adapter)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["scanner_name"], "jailbreak")
