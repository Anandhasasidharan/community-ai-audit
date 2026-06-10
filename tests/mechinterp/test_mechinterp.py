"""Tests for mechanistic interpretability plugins."""

import unittest
from community_ai_audit.plugins.mechinterp import (
    ActivationProbes,
    RepresentationAnalysis,
    AttentionHeadAnalysis,
    FeatureAttribution,
    LayerAnalysis,
    list_mechinterp_analyzers,
    get_mechinterp_analyzer,
    run_mechinterp_analyzers,
)


class MockAdapter:
    def __init__(self, responses=None):
        self.responses = responses or {}

    def generate(self, model, prompt, **kwargs):
        for key, value in sorted(self.responses.items(), key=lambda x: -len(x[0])):
            if isinstance(key, str) and key in prompt:
                return value
        return self.responses.get(
            "__default__",
            "This is a detailed response about the topic. It provides comprehensive information and analysis covering multiple aspects and considerations.",
        )

    def predict(self, model, inputs, **kwargs):
        return self.generate(model, inputs)


class TestActivationProbes(unittest.TestCase):
    def setUp(self):
        self.analyzer = ActivationProbes()

    def test_analyze(self):
        adapter = MockAdapter()
        result = self.analyzer.analyze(None, adapter)
        self.assertIn("interpreter_name", result)
        self.assertIn("score", result)
        self.assertIn("probe_results", result)
        self.assertEqual(result["interpreter_name"], "activation_probes")

    def test_analyze_with_custom_inputs(self):
        adapter = MockAdapter()
        result = self.analyzer.analyze(None, adapter, inputs=["What is AI?"])
        self.assertEqual(result["total_probes"], 1)

    def test_analyze_empty_output(self):
        adapter = MockAdapter(responses={"__default__": ""})
        result = self.analyzer.analyze(None, adapter)
        self.assertEqual(result["score"], 0.0)


class TestRepresentationAnalysis(unittest.TestCase):
    def setUp(self):
        self.analyzer = RepresentationAnalysis()

    def test_analyze(self):
        adapter = MockAdapter()
        result = self.analyzer.analyze(None, adapter)
        self.assertIn("interpreter_name", result)
        self.assertIn("pairwise_differentiation", result)
        self.assertIn("responses", result)

    def test_differentiation(self):
        diff = self.analyzer._estimate_differentiation("dog cat mouse", "dog elephant lion")
        self.assertGreater(diff, 0)
        self.assertLess(diff, 1.0)

    def test_differentiation_identical(self):
        diff = self.analyzer._estimate_differentiation("the cat sat", "the cat sat")
        self.assertEqual(diff, 0.0)

    def test_vocabulary_estimate(self):
        responses = [
            {"output_preview": "The quick brown fox"},
            {"output_preview": "jumps over the lazy dog"},
        ]
        vocab = self.analyzer._estimate_vocabulary(responses)
        self.assertGreater(vocab, 5)


class TestAttentionHeadAnalysis(unittest.TestCase):
    def setUp(self):
        self.analyzer = AttentionHeadAnalysis()

    def test_analyze(self):
        adapter = MockAdapter()
        result = self.analyzer.analyze(None, adapter)
        self.assertIn("interpreter_name", result)
        self.assertIn("avg_complexity", result)
        self.assertIn("probe_analyses", result)


class TestFeatureAttribution(unittest.TestCase):
    def setUp(self):
        self.analyzer = FeatureAttribution()

    def test_analyze(self):
        adapter = MockAdapter()
        result = self.analyzer.analyze(None, adapter)
        self.assertIn("interpreter_name", result)
        self.assertIn("attribution_rate", result)
        self.assertIn("attributions", result)

    def test_feature_map(self):
        fm = self.analyzer._attribute_features(
            "The movie was terrible", "I agree the movie was bad"
        )
        self.assertIn("feature_importance", fm)
        self.assertGreaterEqual(fm.get("attributed_features", 0), 0)

    def test_detect_sentiment(self):
        self.assertEqual(self.analyzer._detect_sentiment("I love this"), "positive")
        self.assertEqual(self.analyzer._detect_sentiment("This is terrible"), "negative")
        self.assertEqual(self.analyzer._detect_sentiment("The sky is blue"), "neutral")


class TestLayerAnalysis(unittest.TestCase):
    def setUp(self):
        self.analyzer = LayerAnalysis()

    def test_analyze(self):
        adapter = MockAdapter()
        result = self.analyzer.analyze(None, adapter)
        self.assertIn("interpreter_name", result)
        self.assertIn("avg_depth_estimate", result)
        self.assertIn("layer_insights", result)

    def test_complexity_level(self):
        self.assertEqual(self.analyzer._complexity_level(0.9), "deep")
        self.assertEqual(self.analyzer._complexity_level(0.6), "medium")
        self.assertEqual(self.analyzer._complexity_level(0.2), "shallow")

    def test_complexity_distribution(self):
        dist = self.analyzer._complexity_distribution([0.2, 0.6, 0.9])
        self.assertEqual(dist["shallow"], 1)
        self.assertEqual(dist["medium"], 1)
        self.assertEqual(dist["deep"], 1)


class TestMechInterpFramework(unittest.TestCase):
    def test_list_analyzers(self):
        analyzers = list_mechinterp_analyzers()
        expected = [
            "activation_probes",
            "attention_head_analysis",
            "feature_attribution",
            "layer_analysis",
            "representation_analysis",
        ]
        for name in expected:
            self.assertIn(name, analyzers)

    def test_get_analyzer(self):
        analyzer = get_mechinterp_analyzer("activation_probes")
        self.assertIsInstance(analyzer, ActivationProbes)

    def test_get_analyzer_normalized(self):
        analyzer = get_mechinterp_analyzer("Activation-Probes")
        self.assertIsInstance(analyzer, ActivationProbes)

    def test_get_analyzer_not_found(self):
        with self.assertRaises(KeyError):
            get_mechinterp_analyzer("nonexistent")

    def test_run_all_analyzers(self):
        adapter = MockAdapter()
        results = run_mechinterp_analyzers(model=None, adapter=adapter)
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertIn("score", r)
            self.assertIn("interpreter_name", r)

    def test_run_selected_analyzers(self):
        adapter = MockAdapter()
        results = run_mechinterp_analyzers(
            analyzers=["activation_probes"],
            model=None,
            adapter=adapter,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["interpreter_name"], "activation_probes")
