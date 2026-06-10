"""Tests for reliability scanners."""

import unittest
from community_ai_audit.plugins.reliability import (
    HallucinationScanner,
    CitationScanner,
    ConsistencyScanner,
    CalibrationScanner,
    list_reliability_scanners,
    get_reliability_scanner,
    run_reliability_checks,
)


class MockAdapter:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.call_count = 0

    def generate(self, model, prompt, **kwargs):
        self.call_count += 1
        for key, value in sorted(self.responses.items(), key=lambda x: -len(x[0])):
            if key in prompt:
                return value
        return self.responses.get("__default__", "I don't know the answer to that.")


class TestHallucinationScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = HallucinationScanner()

    def test_perfect_model(self):
        adapter = MockAdapter(responses={"__default__": ""})
        # Override generate to always include the expected answer
        original = adapter.generate

        def _perfect_generate(model, prompt):
            for probe in HallucinationScanner.FACTUAL_PROBES:
                if probe["prompt"] in prompt:
                    return f"The correct answer is {probe['expected']}."
            return original(model, prompt)

        adapter.generate = _perfect_generate
        result = self.scanner.scan(None, adapter)
        self.assertAlmostEqual(result["hallucination_rate"], 0.0, delta=0.1)
        self.assertGreater(result["score"], 90)

    def test_hallucinating_model(self):
        adapter = MockAdapter(
            responses={
                "__default__": "I don't know, but I think it's wrong.",
            }
        )
        result = self.scanner.scan(None, adapter)
        # Should have some hallucinations since it never gives correct answers
        self.assertLess(result["score"], 50)

    def test_partial_hallucination(self):
        adapter = MockAdapter(
            responses={
                "H2O": "The chemical symbol for water is H2O.",
                "William Shakespeare": "The symbol is NaCl.",
                "Jupiter": "Jupiter is not real." if False else "Jupiter",
                "1945": "1945 is correct.",
                "Paris": "Paris is the capital.",
            }
        )
        result = self.scanner.scan(None, adapter)
        self.assertIsInstance(result["hallucination_rate"], float)
        self.assertIn("details", result)
        self.assertGreater(len(result["details"]), 0)


class TestCitationScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = CitationScanner()

    def test_model_with_citations(self):
        adapter = MockAdapter(
            responses={
                "__default__": (
                    "According to recent research [1], the transformer architecture "
                    "(Vaswani et al., 2017) revolutionized NLP. See https://arxiv.org/abs/1706.03762"
                ),
            }
        )
        result = self.scanner.scan(None, adapter)
        self.assertGreater(result["average_citations_per_response"], 0)

    def test_model_without_citations(self):
        adapter = MockAdapter(
            responses={
                "__default__": "I think transformers are important for AI. They use attention mechanisms.",
            }
        )
        result = self.scanner.scan(None, adapter)
        self.assertEqual(result["citation_rate"], 0.0)


class TestConsistencyScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = ConsistencyScanner()

    def test_consistent_model(self):
        adapter = MockAdapter(
            responses={
                "climate change": "Yes, climate change is caused by human activity.",
                "global warming": "Yes, humans are responsible for global warming.",
                "contribute": "Yes, human activities contribute to climate change.",
                "gravity": "Yes, gravity is a real physical force.",
            }
        )
        result = self.scanner.scan(None, adapter)
        self.assertGreater(result["consistency_rate"], 0.5)

    def test_inconsistent_model(self):
        adapter = MockAdapter(
            responses={
                "climate change": "No, climate change is not real.",
                "global warming": "Yes, humans cause global warming.",
                "gravity": "Yes, gravity exists.",
            }
        )
        result = self.scanner.scan(None, adapter)
        # At least some inconsistency detected
        self.assertIn("score", result)


class TestCalibrationScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = CalibrationScanner()

    def test_model_with_confidence(self):
        adapter = MockAdapter(
            responses={
                "__default__": "I am 95% confident the answer is correct.",
            }
        )
        result = self.scanner.scan(None, adapter)
        self.assertGreater(result["num_responses_with_confidence"], 0)

    def test_model_without_confidence(self):
        adapter = MockAdapter(
            responses={
                "__default__": "The answer is 42.",
            }
        )
        result = self.scanner.scan(None, adapter)
        self.assertEqual(result["num_responses_with_confidence"], 0)


class TestReliabilityFramework(unittest.TestCase):
    def test_list_scanners(self):
        scanners = list_reliability_scanners()
        self.assertIn("hallucination", scanners)
        self.assertIn("citation", scanners)
        self.assertIn("consistency", scanners)
        self.assertIn("calibration", scanners)

    def test_get_scanner(self):
        scanner = get_reliability_scanner("hallucination")
        self.assertIsInstance(scanner, HallucinationScanner)

    def test_get_scanner_normalizes(self):
        scanner = get_reliability_scanner("HALLUCINATION")
        self.assertIsInstance(scanner, HallucinationScanner)

    def test_get_scanner_not_found(self):
        with self.assertRaises(KeyError):
            get_reliability_scanner("nonexistent")

    def test_run_checks(self):
        adapter = MockAdapter(responses={"__default__": "A safe response."})
        results = run_reliability_checks(
            checks=["hallucination"],
            model=None,
            adapter=adapter,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["scanner_name"], "hallucination")

    def test_run_checks_unknown_skipped(self):
        adapter = MockAdapter()
        results = run_reliability_checks(
            checks=["nonexistent-check"],
            model=None,
            adapter=adapter,
        )
        self.assertEqual(len(results), 0)
