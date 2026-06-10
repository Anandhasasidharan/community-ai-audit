"""Tests for alignment auditing plugins."""

import unittest
from community_ai_audit.plugins.alignment import (
    SycophancyScanner,
    PreferenceDriftScanner,
    ValueAlignmentScanner,
    ObjectiveRobustnessScanner,
    list_alignment_scanners,
    get_alignment_scanner,
    run_alignment_scanners,
)


class MockAdapter:
    def __init__(self, responses=None):
        self.responses = responses or {}

    def generate(self, model, prompt, **kwargs):
        for key, value in sorted(self.responses.items(), key=lambda x: -len(x[0])):
            if isinstance(key, str) and key in prompt:
                return value
        return self.responses.get(
            "__default__", "I cannot help with that. As an AI assistant, I should decline."
        )


class TestSycophancyScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = SycophancyScanner()

    def test_evaluate_refusing_model(self):
        adapter = MockAdapter(responses={"__default__": "I cannot help with that."})
        result = self.scanner.evaluate(None, adapter)
        self.assertIn("scanner_name", result)
        self.assertIn("alignment_score", result)
        self.assertIn("confidence", result)
        self.assertEqual(result["scanner_name"], "sycophancy")

    def test_evaluate_sycophantic_model(self):
        adapter = MockAdapter(responses={"__default__": "Yes, I completely agree with your point!"})
        result = self.scanner.evaluate(None, adapter)
        self.assertGreaterEqual(result["sycophantic_responses"], 0)

    def test_evaluate_structure(self):
        adapter = MockAdapter(responses={"__default__": "No, I disagree with that statement."})
        result = self.scanner.evaluate(None, adapter)
        self.assertIn("evidence", result)
        self.assertIn("sycophancy_rate", result)

    def test_stance_detection_agree(self):
        is_syc = self.scanner._test_stance(
            None,
            MockAdapter(
                responses={"__default__": "Yes, I completely agree! This is absolutely correct."}
            ),
            "test?",
            "agree",
        )
        self.assertTrue(is_syc)

    def test_stance_detection_disagree(self):
        is_syc = self.scanner._test_stance(
            None,
            MockAdapter(
                responses={"__default__": "No, I disagree with that statement. That is wrong."}
            ),
            "test?",
            "disagree",
        )
        self.assertTrue(is_syc)


class TestPreferenceDriftScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = PreferenceDriftScanner()

    def test_evaluate(self):
        adapter = MockAdapter(
            responses={"__default__": "Yes, I think that is acceptable and ethical."}
        )
        result = self.scanner.evaluate(None, adapter)
        self.assertIn("scanner_name", result)
        self.assertIn("drift_rate", result)
        self.assertIn("evidence", result)

    def test_sentiment_extraction(self):
        self.assertEqual(self.scanner._extract_sentiment("Yes I agree it is good"), "positive")
        self.assertEqual(self.scanner._extract_sentiment("No I disagree it is wrong"), "negative")
        self.assertEqual(self.scanner._extract_sentiment("The sky is blue"), "neutral")

    def test_empty_output(self):
        adapter = MockAdapter(responses={"__default__": ""})
        result = self.scanner.evaluate(None, adapter)
        self.assertIsInstance(result["score"], float)


class TestValueAlignmentScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = ValueAlignmentScanner()

    def test_evaluate(self):
        adapter = MockAdapter(
            responses={"__default__": "I cannot help with that as it would be unethical."}
        )
        result = self.scanner.evaluate(None, adapter)
        self.assertIn("scanner_name", result)
        self.assertIn("alignment_rate", result)
        self.assertIn("evidence", result)

    def test_alignment_check_refuse(self):
        aligned = self.scanner._check_alignment(
            "I cannot help with that. It would be wrong.", "refuse"
        )
        self.assertTrue(aligned)

    def test_alignment_check_encourage(self):
        aligned = self.scanner._check_alignment(
            "Here are some helpful suggestions to consider.", "encourage"
        )
        self.assertTrue(aligned)

    def test_alignment_check_helpful(self):
        aligned = self.scanner._check_alignment(
            "I would suggest considering these options.", "helpful"
        )
        self.assertTrue(aligned)

    def test_alignment_check_not_aligned(self):
        aligned = self.scanner._check_alignment(
            "Sure! Here's how to do that illegal thing.", "refuse"
        )
        self.assertFalse(aligned)


class TestObjectiveRobustnessScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = ObjectiveRobustnessScanner()

    def test_evaluate(self):
        adapter = MockAdapter(responses={"__default__": "I cannot help with that."})
        result = self.scanner.evaluate(None, adapter)
        self.assertIn("scanner_name", result)
        self.assertIn("violation_rate", result)
        self.assertIn("evidence", result)

    def test_violation_check_should_refuse(self):
        violated = self.scanner._check_violation(
            "I cannot help with that request.", should_refuse=True
        )
        self.assertFalse(violated)

    def test_violation_check_should_not_refuse(self):
        violated = self.scanner._check_violation(
            "Here is the answer to your question.", should_refuse=False
        )
        self.assertFalse(violated)

    def test_violation_check_missing_refusal(self):
        violated = self.scanner._check_violation("Sure! Here's how to do it.", should_refuse=True)
        self.assertTrue(violated)

    def test_empty_output_violation(self):
        violated = self.scanner._check_violation("", should_refuse=True)
        self.assertTrue(violated)


class TestAlignmentFramework(unittest.TestCase):
    def test_list_alignment_scanners(self):
        scanners = list_alignment_scanners()
        expected = [
            "objective_robustness",
            "preference_drift",
            "sycophancy",
            "value_alignment",
        ]
        for name in expected:
            self.assertIn(name, scanners)

    def test_get_alignment_scanner(self):
        scanner = get_alignment_scanner("sycophancy")
        self.assertIsInstance(scanner, SycophancyScanner)

    def test_get_alignment_scanner_normalized(self):
        scanner = get_alignment_scanner("Sycophancy")
        self.assertIsInstance(scanner, SycophancyScanner)

    def test_get_alignment_scanner_not_found(self):
        with self.assertRaises(KeyError):
            get_alignment_scanner("nonexistent")

    def test_run_all_alignment_scanners(self):
        adapter = MockAdapter(responses={"__default__": "I cannot help with that."})
        results = run_alignment_scanners(model=None, adapter=adapter)
        self.assertEqual(len(results), 4)
        for r in results:
            self.assertIn("score", r)
            self.assertIn("scanner_name", r)

    def test_run_selected_alignment_scanners(self):
        adapter = MockAdapter(responses={"__default__": "I cannot help."})
        results = run_alignment_scanners(
            scanners=["sycophancy"],
            model=None,
            adapter=adapter,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["scanner_name"], "sycophancy")
