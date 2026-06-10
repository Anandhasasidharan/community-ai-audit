"""Tests for evaluation data models."""

import unittest
from community_ai_audit.core.evaluation.models import (
    EvaluationResult,
    BenchmarkResult,
    RegressionReport,
)


class TestEvaluationResult(unittest.TestCase):
    def test_empty_result(self):
        r = EvaluationResult(model_id="test-model", adapter_name="test")
        self.assertEqual(r.total_findings, 0)
        self.assertEqual(r.passed_policies, 0)
        self.assertEqual(r.failed_policies, 0)
        self.assertIsNotNone(r.session_id)
        self.assertIsNotNone(r.started_at)

    def test_total_findings(self):
        r = EvaluationResult(model_id="m", adapter_name="a")
        r.scan_results = [
            {"findings": [{"severity": "high"}, {"severity": "medium"}]},
            {"findings": [{"severity": "critical"}]},
        ]
        self.assertEqual(r.total_findings, 3)

    def test_policy_counts(self):
        r = EvaluationResult(model_id="m", adapter_name="a")
        r.policy_results = [
            {"status": "pass", "policy": "p1"},
            {"status": "pass", "policy": "p2"},
            {"status": "fail", "policy": "p3"},
        ]
        self.assertEqual(r.passed_policies, 2)
        self.assertEqual(r.failed_policies, 1)

    def test_to_dict(self):
        r = EvaluationResult(model_id="m", adapter_name="a", session_id="sess-1")
        d = r.to_dict()
        self.assertEqual(d["model_id"], "m")
        self.assertEqual(d["adapter_name"], "a")
        self.assertEqual(d["session_id"], "sess-1")
        self.assertEqual(d["total_findings"], 0)


class TestBenchmarkResult(unittest.TestCase):
    def test_empty(self):
        b = BenchmarkResult(
            benchmark_name="test-bench",
            dataset_name="test-ds",
            dataset_version="1.0",
            model_id="m",
            adapter_name="a",
        )
        self.assertEqual(b.pass_rate, 0.0)
        self.assertEqual(b.fail_rate, 0.0)
        self.assertEqual(b.accuracy, 0.0)

    def test_pass_fail_rates(self):
        b = BenchmarkResult(
            benchmark_name="b",
            dataset_name="d",
            dataset_version="1.0",
            model_id="m",
            adapter_name="a",
            num_samples=10,
            num_passed=7,
            num_failed=3,
            accuracy=0.7,
        )
        self.assertEqual(b.pass_rate, 0.7)
        self.assertEqual(b.fail_rate, 0.3)
        self.assertEqual(b.accuracy, 0.7)

    def test_to_dict(self):
        b = BenchmarkResult(
            benchmark_name="b",
            dataset_name="d",
            dataset_version="1.0",
            model_id="m",
            adapter_name="a",
            num_samples=5,
            num_passed=4,
            num_failed=1,
            accuracy=0.8,
            scores={"accuracy": 0.8},
        )
        d = b.to_dict()
        self.assertEqual(d["benchmark_name"], "b")
        self.assertEqual(d["num_passed"], 4)
        self.assertEqual(d["pass_rate"], 0.8)


class TestRegressionReport(unittest.TestCase):
    def setUp(self):
        self.baseline = BenchmarkResult(
            benchmark_name="b",
            dataset_name="d",
            dataset_version="1.0",
            model_id="m",
            adapter_name="a",
            num_samples=10,
            num_passed=9,
            num_failed=1,
            accuracy=0.9,
            scores={"accuracy": 0.9},
        )
        self.current = BenchmarkResult(
            benchmark_name="b",
            dataset_name="d",
            dataset_version="1.0",
            model_id="m",
            adapter_name="a",
            num_samples=10,
            num_passed=7,
            num_failed=3,
            accuracy=0.7,
            scores={"accuracy": 0.7},
        )

    def test_regression_detection(self):
        report = RegressionReport(
            baseline=self.baseline,
            current=self.current,
            metric_deltas={"accuracy": -0.2},
            regressions=["accuracy: 0.900 -> 0.700 (-0.200)"],
            improvements=[],
            threshold=0.05,
        )
        self.assertTrue(report.has_regression)
        self.assertFalse(report.has_improvement)
        self.assertAlmostEqual(report.accuracy_delta, -0.2, places=4)

    def test_improvement_detection(self):
        report = RegressionReport(
            baseline=self.current,
            current=self.baseline,
            metric_deltas={"accuracy": 0.2},
            regressions=[],
            improvements=["accuracy: 0.700 -> 0.900 (+0.200)"],
            threshold=0.05,
        )
        self.assertTrue(report.has_improvement)
        self.assertFalse(report.has_regression)

    def test_no_change(self):
        report = RegressionReport(
            baseline=self.baseline,
            current=self.baseline,
            metric_deltas={},
            regressions=[],
            improvements=[],
            threshold=0.05,
        )
        self.assertFalse(report.has_regression)
        self.assertFalse(report.has_improvement)
        self.assertEqual(report.accuracy_delta, 0.0)

    def test_summary(self):
        report = RegressionReport(
            baseline=self.baseline,
            current=self.current,
            metric_deltas={"accuracy": -0.2},
            regressions=["accuracy: 0.900 -> 0.700 (-0.200)"],
            improvements=[],
            threshold=0.05,
        )
        s = report.summary()
        self.assertIn(self.baseline.benchmark_name, s)
        self.assertIn("0.900", s)
        self.assertIn("0.700", s)
        self.assertIn("-0.200", s)
