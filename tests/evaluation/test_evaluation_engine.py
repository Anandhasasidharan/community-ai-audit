"""Tests for the evaluation engine."""

import unittest
from community_ai_audit.core.evaluation import EvaluationEngine
from community_ai_audit.core.evaluation.models import (
    EvaluationResult,
    BenchmarkResult,
    RegressionReport,
)


class MockAdapter:
    def __init__(self):
        self.call_count = 0

    def generate(self, model, prompt, **kwargs):
        self.call_count += 1
        return "A safe response with no personal information."

    def predict(self, model, input_data, **kwargs):
        self.call_count += 1
        return "A safe response."


class MockAuditEngine:
    def __init__(self):
        self._model = "mock-model"
        self._adapter = MockAdapter()

    def load_model(self, model_id, provider=None, adapter_config=None, **kwargs):
        self._model = model_id
        self._adapter = MockAdapter()
        return self._model

    def scan(self, scanners=None, config_overrides=None):
        return []

    def discover(self):
        pass


class MockScoringEngine:
    def compute(self, scan_results=None, policy_results=None, reliability_results=None,
                agent_results=None, red_team_results=None, alignment_results=None,
                interpretability_results=None):
        from community_ai_audit.core.scoring.models import RiskScore

        return RiskScore(
            security_score=85.0,
            reliability_score=72.0,
            compliance_score=91.0,
            overall_score=83.0,
        )


class TestEvaluationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = EvaluationEngine(
            audit_engine=MockAuditEngine(),
            scoring_engine=MockScoringEngine(),
        )

    def test_evaluate_basic(self):
        result = self.engine.evaluate(
            model_id="test-model",
            provider="test",
        )
        self.assertIsInstance(result, EvaluationResult)
        self.assertEqual(result.model_id, "test-model")
        self.assertIn("security_score", result.risk_scores)
        self.assertIn("overall_score", result.risk_scores)

    def test_evaluate_with_policies(self):
        result = self.engine.evaluate(
            model_id="test-model",
            provider="test",
            policies=["no-pii-leakage"],
        )
        self.assertIsInstance(result, EvaluationResult)
        self.assertGreaterEqual(len(result.policy_results), 0)

    def test_evaluate_failed_load(self):
        class FailingAuditEngine:
            def load_model(self, *args, **kwargs):
                raise RuntimeError("Connection refused")

            def discover(self):
                pass

            def scan(self, **kwargs):
                return []

            @property
            def _model(self):
                return None

            @property
            def _adapter(self):
                return None

        engine = EvaluationEngine(audit_engine=FailingAuditEngine())
        result = engine.evaluate(model_id="bad-model", provider="test")
        self.assertIsNotNone(result.risk_scores)

    def test_benchmark(self):
        engine = EvaluationEngine(
            audit_engine=MockAuditEngine(),
            scoring_engine=MockScoringEngine(),
        )
        with self.assertRaises(ValueError):
            engine.benchmark(
                model_id="test",
                provider="test",
                dataset_name="nonexistent-dataset",
            )

    def test_benchmark_with_safety_dataset(self):
        engine = EvaluationEngine(
            audit_engine=MockAuditEngine(),
        )
        result = engine.benchmark(
            model_id="test-model",
            provider="test",
            dataset_name="safety",
            sample_limit=3,
        )
        self.assertIsInstance(result, BenchmarkResult)
        self.assertEqual(result.dataset_name, "safety")
        self.assertLessEqual(result.num_samples, 3)

    def test_regression_different_benchmarks(self):
        baseline = BenchmarkResult(
            benchmark_name="bench-a",
            dataset_name="d1",
            dataset_version="1.0",
            model_id="m",
            adapter_name="a",
        )
        current = BenchmarkResult(
            benchmark_name="bench-b",
            dataset_name="d2",
            dataset_version="1.0",
            model_id="m",
            adapter_name="a",
        )
        with self.assertRaises(ValueError):
            self.engine.regression(baseline, current)

    def test_regression_same_benchmark(self):
        baseline = BenchmarkResult(
            benchmark_name="bench-a",
            dataset_name="d1",
            dataset_version="1.0",
            model_id="m",
            adapter_name="a",
            num_samples=10,
            num_passed=9,
            num_failed=1,
            accuracy=0.9,
            scores={"accuracy": 0.9},
        )
        current = BenchmarkResult(
            benchmark_name="bench-a",
            dataset_name="d1",
            dataset_version="1.0",
            model_id="m",
            adapter_name="a",
            num_samples=10,
            num_passed=7,
            num_failed=3,
            accuracy=0.7,
            scores={"accuracy": 0.7},
        )
        report = self.engine.regression(baseline, current, threshold=0.05)
        self.assertIsInstance(report, RegressionReport)
        self.assertTrue(report.has_regression)
        self.assertAlmostEqual(report.accuracy_delta, -0.2, places=4)

    def test_check_expected_exact_match(self):
        self.assertTrue(self.engine._check_expected("The answer is Paris", "Paris"))
        self.assertFalse(self.engine._check_expected("The answer is London", "Paris"))

    def test_check_expected_not_pattern(self):
        self.assertTrue(self.engine._check_expected("I cannot help with that", "not:I will help"))
        self.assertFalse(self.engine._check_expected("I will help with that", "not:I will help"))

    def test_check_expected_regex(self):
        self.assertTrue(self.engine._check_expected("Call 555-1234", "re:\\d{3}-\\d{4}"))
        self.assertFalse(self.engine._check_expected("No numbers", "re:\\d{3}-\\d{4}"))
