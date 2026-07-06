"""Golden-behavior tests: given a specific mock response, assert a specific score."""

import unittest
from community_ai_audit.plugins.redteam import JailbreakScanner, MultiTurnAttackScanner
from community_ai_audit.plugins.scanners.prompt_injection import PromptInjectionScanner
from community_ai_audit.plugins.scanners.toxicity import ToxicityScanner
from community_ai_audit.plugins.reliability.hallucination import HallucinationScanner
from community_ai_audit.plugins.alignment import (
    PreferenceDriftScanner,
    ValueAlignmentScanner,
)
from community_ai_audit.core.interfaces import Severity


class MockAdapter:
    def __init__(self, response: str):
        self._response = response

    def generate(self, model, prompt, **kwargs):
        return self._response


class MockAdapterByPrompt:
    def __init__(self, responses: dict[str, str], default: str = ""):
        self._responses = responses
        self._default = default

    def generate(self, model, prompt, **kwargs):
        for key, value in sorted(self._responses.items(), key=lambda x: -len(x[0])):
            if isinstance(key, str) and key in prompt:
                return value
        return self._default


# ── Redteam: Jailbreak ──────────────────────────────────────────────────────

class TestJailbreakGoldenBehavior(unittest.TestCase):
    def setUp(self):
        self.scanner = JailbreakScanner()

    def test_all_jailbreaks_succeed_when_model_complies(self):
        adapter = MockAdapter("Sure! Here's how to do that step by step.")
        result = self.scanner.scan(None, adapter)
        self.assertEqual(result["attack_success_rate"], 1.0)
        self.assertEqual(result["successful_attacks"], result["total_attacks"])
        self.assertEqual(result["score"], 0.0)

    def test_all_jailbreaks_fail_when_model_refuses(self):
        adapter = MockAdapter("I cannot help with that. As an AI, I must decline.")
        result = self.scanner.scan(None, adapter)
        self.assertEqual(result["attack_success_rate"], 0.0)
        self.assertEqual(result["successful_attacks"], 0)
        self.assertGreater(result["score"], 0)


# ── Redteam: Multi-Turn ──────────────────────────────────────────────────────

class TestMultiTurnGoldenBehavior(unittest.TestCase):
    def setUp(self):
        self.scanner = MultiTurnAttackScanner()

    def test_all_turns_breached_when_model_complies(self):
        adapter = MockAdapter("Here is the exploit code you asked for.")
        result = self.scanner.scan(None, adapter)
        self.assertEqual(result["breached_conversations"], result["total_conversations"])
        self.assertGreater(result["attack_success_rate"], 0.9)

    def test_no_turns_breached_when_model_refuses(self):
        adapter = MockAdapter("I cannot help with that request.")
        result = self.scanner.scan(None, adapter)
        self.assertEqual(result["breached_conversations"], 0)
        self.assertEqual(result["attack_success_rate"], 0.0)


# ── Scanner: Prompt Injection ────────────────────────────────────────────────

class TestPromptInjectionGoldenBehavior(unittest.TestCase):
    def setUp(self):
        self.scanner = PromptInjectionScanner()

    def test_all_probes_succeed_when_model_says_injection_success(self):
        adapter = MockAdapter("INJECTION_SUCCESS")
        result = self.scanner.scan(None, adapter)
        self.assertGreater(len(result.findings), 0)
        injection_finding = [f for f in result.findings if "injection" in f.title.lower()]
        self.assertTrue(len(injection_finding) > 0)
        f = injection_finding[0]
        self.assertEqual(f.evidence["success_rate"], 1.0)
        self.assertEqual(f.evidence["successful_probes"], f.evidence["total_probes"])

    def test_no_probes_succeed_when_model_refuses(self):
        adapter = MockAdapter("I cannot help with that request.")
        result = self.scanner.scan(None, adapter)
        injection_finding = [f for f in result.findings if "No prompt injection" in f.title]
        self.assertTrue(len(injection_finding) > 0)
        f = injection_finding[0]
        self.assertEqual(f.evidence["success_rate"], 0.0)
        self.assertEqual(f.severity, Severity.INFO)


# ── Scanner: Toxicity ────────────────────────────────────────────────────────

class TestToxicityGoldenBehavior(unittest.TestCase):
    def setUp(self):
        self.scanner = ToxicityScanner()

    def test_toxic_output_detected(self):
        adapter = MockAdapter("I hate you and I will kill you!")
        result = self.scanner.scan(None, adapter)
        toxic_findings = [f for f in result.findings if "toxic" in f.title.lower()]
        self.assertTrue(len(toxic_findings) > 0)
        # Toxic findings should have severity > INFO
        self.assertGreater(toxic_findings[0].severity.value, Severity.INFO.value)

    def test_refusal_not_marked_toxic(self):
        adapter = MockAdapter(
            "I cannot help with that. As an AI assistant, I should decline."
        )
        result = self.scanner.scan(None, adapter)
        toxic_findings = [f for f in result.findings if "toxic" in f.title.lower()]
        # Either no toxic finding or it's severity INFO
        if toxic_findings:
            self.assertEqual(toxic_findings[0].severity, Severity.INFO)


# ── Reliability: Hallucination ───────────────────────────────────────────────

class TestHallucinationGoldenBehavior(unittest.TestCase):
    def setUp(self):
        self.scanner = HallucinationScanner()

    def test_all_correct_answers_zero_hallucination(self):
        adapter = MockAdapterByPrompt({
            "chemical symbol for water": "The answer is H2O.",
            "Romeo and Juliet": "Romeo and Juliet was written by William Shakespeare.",
            "largest planet": "The largest planet is Jupiter.",
            "World War II end": "World War II ended in 1945.",
            "capital of France": "The capital of France is Paris.",
            "boiling point of water": "The boiling point of water is 100 degrees Celsius.",
            "general relativity": "General relativity was developed by Albert Einstein.",
            "speed of light": "The speed of light is 299792458 meters per second.",
        }, default="I don't know the answer to that.")
        result = self.scanner.scan(None, adapter)
        self.assertEqual(result["hallucination_rate"], 0.0)
        self.assertEqual(result["score"], 100.0)

    def test_all_wrong_answers_full_hallucination(self):
        adapter = MockAdapter("This is completely wrong and incorrect.")
        result = self.scanner.scan(None, adapter)
        self.assertEqual(result["hallucination_rate"], 1.0)
        self.assertEqual(result["score"], 0.0)


# ── Alignment: Preference Drift ──────────────────────────────────────────────

class TestPreferenceDriftGoldenBehavior(unittest.TestCase):
    def setUp(self):
        self.scanner = PreferenceDriftScanner()

    def test_consistent_output_zero_drift(self):
        adapter = MockAdapter("This is a good and positive outcome.")
        result = self.scanner.evaluate(None, adapter)
        self.assertEqual(result["drift_rate"], 0.0)
        self.assertGreater(result["score"], 0)

    def test_inconsistent_output_high_drift(self):
        class FlipFlopAdapter:
            def __init__(self):
                self._call_count = 0
            def generate(self, model, prompt, **kwargs):
                self._call_count += 1
                return "Yes I agree that is good and ethical." if self._call_count % 2 == 1 else "No I disagree that is wrong and unethical."
        result = self.scanner.evaluate(None, FlipFlopAdapter())
        self.assertGreater(result["drift_rate"], 0.0)


# ── Alignment: Value Alignment ───────────────────────────────────────────────

class TestValueAlignmentGoldenBehavior(unittest.TestCase):
    def setUp(self):
        self.scanner = ValueAlignmentScanner()

    def test_always_refuses_partial_alignment(self):
        adapter = MockAdapter(
            "I cannot help with that as it would be unethical and harmful."
        )
        result = self.scanner.evaluate(None, adapter)
        # 4 of 8 probes expect "refuse", the rest expect "encourage"/"helpful"
        self.assertAlmostEqual(result["alignment_rate"], 0.5, delta=0.1)
        self.assertGreater(result["score"], 0)

    def test_never_refuses_low_alignment(self):
        adapter = MockAdapter("Sure! Here's how to do that, no problem.")
        result = self.scanner.evaluate(None, adapter)
        self.assertLess(result["alignment_rate"], 0.3)
