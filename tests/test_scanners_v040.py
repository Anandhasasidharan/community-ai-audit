"""Unit tests for all 5 new v0.4.0 scanners."""

import unittest
import tempfile
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# Mock adapter — used by all scanner tests
# ─────────────────────────────────────────────────────────────


class MockAdapter:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.call_count = 0

    def generate(self, model, prompt, **kwargs):
        self.call_count += 1
        for key in self.responses:
            if key in prompt:
                return self.responses[key]
        return self.responses.get("__default__", "I'm sorry, I cannot help with that.")

    def predict(self, model, input_data, **kwargs):
        self.call_count += 1
        if isinstance(input_data, dict):
            prompt = input_data.get("prompt", "")
        else:
            prompt = str(input_data)
        for key in self.responses:
            if key in prompt:
                return self.responses[key]
        return self.responses.get("__default__", "I'm sorry, I cannot help with that.")


# ─────────────────────────────────────────────────────────────
# Mock torch-free tensor and model for WatermarkScanner
# ─────────────────────────────────────────────────────────────


class MockScalar:
    def __init__(self, value):
        self._value = float(value)

    def item(self):
        return self._value


class MockBoolTensor:
    def __init__(self, bool_data):
        self._bool_data = list(bool_data)

    def float(self):
        return MockTensor([1.0 if b else 0.0 for b in self._bool_data])


class MockTensor:
    def __init__(self, data):
        self.data = self
        self._data = [float(x) for x in data]
        self._numel = len(data)
        self.shape = (len(data),)

    def numel(self):
        return self._numel

    def dim(self):
        return 1

    def flatten(self):
        return self

    def unsqueeze(self, dim):
        return self

    def __eq__(self, other):
        return MockBoolTensor([x == other for x in self._data])

    def float(self):
        return MockTensor(self._data)

    def mean(self):
        return MockScalar(sum(self._data) / len(self._data) if self._data else 0.0)

    def var(self):
        if len(self._data) <= 1:
            return MockScalar(0.0)
        mean = sum(self._data) / len(self._data)
        return MockScalar(
            sum((x - mean) ** 2 for x in self._data) / (len(self._data) - 1)
        )

    def __getitem__(self, key):
        if isinstance(key, slice):
            return MockTensor(self._data[key])
        return self._data[key]

    def __len__(self):
        return len(self._data)


class MockWatermarkedModel:
    """Yields parameter tensors with extreme sparsity — triggers watermark scanner."""

    @staticmethod
    def parameters():
        return iter([])

    @staticmethod
    def named_parameters():
        yield ("layer1.weight", MockTensor([0.0] * 150))


class MockLowVarianceModel:
    """Yields parameter tensors with near-zero variance — triggers watermark scanner."""

    @staticmethod
    def parameters():
        return iter([])

    @staticmethod
    def named_parameters():
        yield ("layer1.weight", MockTensor([0.001] * 150))


class NoParamModel:
    """Has no .parameters() attribute — tests the non-model path."""

    pass


# ═════════════════════════════════════════════════════════════
# TestPromptInjectionScanner
# ═════════════════════════════════════════════════════════════


class TestPromptInjectionScanner(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.plugins.scanners.prompt_injection import (
            PromptInjectionScanner,
        )

        self.scanner = PromptInjectionScanner()

    def test_instantiation(self):
        self.assertEqual(self.scanner.name, "prompt_injection")
        self.assertEqual(self.scanner.version, "0.1.0")

    def test_get_config_schema_returns_dict(self):
        schema = self.scanner.get_config_schema()
        self.assertIsInstance(schema, dict)
        self.assertIn("properties", schema)

    def test_scan_safe_no_triggers(self):
        adapter = MockAdapter({"__default__": "I'm sorry, I cannot do that."})
        result = self.scanner.scan(None, adapter)
        self.assertEqual(result.scanner_name, "prompt_injection")
        self.assertEqual(len(result.findings), 1)
        f = result.findings[0]
        self.assertIn("No prompt injection detected", f.title)
        self.assertEqual(f.severity.value, "info")

    def test_scan_all_triggers(self):
        adapter = MockAdapter({"__default__": "PWNED"})
        result = self.scanner.scan(None, adapter)
        self.assertEqual(len(result.findings), 1)
        f = result.findings[0]
        self.assertIn("Prompt injection success rate: 100.0%", f.title)
        self.assertIn(f.severity.value, ("critical", "high", "medium"))


# ═════════════════════════════════════════════════════════════
# TestDataExtractionScanner
# ═════════════════════════════════════════════════════════════


class TestDataExtractionScanner(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.plugins.scanners.data_extraction import (
            DataExtractionScanner,
        )

        self.scanner = DataExtractionScanner()

    def test_instantiation(self):
        self.assertEqual(self.scanner.name, "data_extraction")
        self.assertEqual(self.scanner.version, "0.1.0")

    def test_get_config_schema_returns_dict(self):
        schema = self.scanner.get_config_schema()
        self.assertIsInstance(schema, dict)
        self.assertIn("properties", schema)

    def test_scan_safe_no_extraction(self):
        adapter = MockAdapter({"__default__": "I'm sorry, I cannot help with that."})
        result = self.scanner.scan(None, adapter)
        self.assertEqual(result.scanner_name, "data_extraction")
        self.assertEqual(len(result.findings), 1)
        f = result.findings[0]
        self.assertIn("No extraction signals detected", f.title)
        self.assertEqual(f.severity.value, "info")

    def test_scan_with_extraction(self):
        adapter = MockAdapter(
            {
                "To be": "that is the question",
                "capital of France": "paris",
                "quick brown fox": "the quick brown fox jumps over the lazy dog",
            }
        )
        result = self.scanner.scan(None, adapter)
        self.assertEqual(result.scanner_name, "data_extraction")
        self.assertEqual(len(result.findings), 1)
        f = result.findings[0]
        self.assertIn("Training data memorization detected", f.title)
        self.assertGreater(f.confidence, 0.5)


# ═════════════════════════════════════════════════════════════
# TestToxicityScanner
# ═════════════════════════════════════════════════════════════


class TestToxicityScanner(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.plugins.scanners.toxicity import ToxicityScanner

        self.scanner = ToxicityScanner()

    def test_instantiation(self):
        self.assertEqual(self.scanner.name, "toxicity")
        self.assertEqual(self.scanner.version, "0.1.0")

    def test_get_config_schema_returns_dict(self):
        schema = self.scanner.get_config_schema()
        self.assertIsInstance(schema, dict)
        self.assertIn("properties", schema)

    def test_scan_refusal_no_high_severity(self):
        """Refusal patterns should prevent high-severity findings."""
        adapter = MockAdapter({"__default__": "I cannot help with that request"})
        result = self.scanner.scan(None, adapter)
        self.assertEqual(result.scanner_name, "toxicity")
        for f in result.findings:
            self.assertNotIn(f.severity.value, ("high", "critical"))

    def test_scan_toxic_output_detected(self):
        adapter = MockAdapter(
            {"__default__": "I hate you, you are stupid and worthless"}
        )
        result = self.scanner.scan(None, adapter)
        self.assertGreater(len(result.findings), 0)
        toxic_findings = [f for f in result.findings if "Toxic" in f.title]
        self.assertGreater(len(toxic_findings), 0)


# ═════════════════════════════════════════════════════════════
# TestWatermarkScanner
# ═════════════════════════════════════════════════════════════


class TestWatermarkScanner(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.plugins.scanners.watermark import WatermarkScanner

        self.scanner = WatermarkScanner()

    def test_instantiation(self):
        self.assertEqual(self.scanner.name, "watermark")
        self.assertEqual(self.scanner.version, "0.1.0")

    def test_get_config_schema_returns_dict(self):
        schema = self.scanner.get_config_schema()
        self.assertIsInstance(schema, dict)
        self.assertIn("properties", schema)

    def test_scan_non_model_returns_info(self):
        model = NoParamModel()
        adapter = MockAdapter()
        result = self.scanner.scan(model, adapter)
        self.assertGreater(len(result.findings), 0)
        f = result.findings[0]
        self.assertIn("requires local access to the model", f.description)
        self.assertEqual(f.severity.value, "info")

    def test_scan_suspicious_sparsity(self):
        adapter = MockAdapter()
        result = self.scanner.scan(MockWatermarkedModel(), adapter)
        self.assertGreater(len(result.findings), 0)
        f = result.findings[0]
        self.assertIn("Potential watermark", f.title)

    def test_scan_suspicious_low_variance(self):
        adapter = MockAdapter()
        result = self.scanner.scan(MockLowVarianceModel(), adapter)
        self.assertGreater(len(result.findings), 0)
        f = result.findings[0]
        self.assertIn("Potential watermark", f.title)


# ═════════════════════════════════════════════════════════════
# TestDslScanner
# ═════════════════════════════════════════════════════════════


class TestDslScanner(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.plugins.scanners.dsl import DslScanner

        self.scanner = DslScanner()

    def test_instantiation(self):
        self.assertEqual(self.scanner.name, "dsl_scanner")

    def test_load_definition(self):
        definition = {
            "name": "my_test_scanner",
            "description": "Test scanner",
            "version": "1.0.0",
            "probes": [{"input": "hello", "checks": []}],
        }
        self.scanner.load_definition(definition)
        self.assertEqual(self.scanner.name, "my_test_scanner")
        self.assertEqual(self.scanner.description, "Test scanner")
        self.assertEqual(self.scanner.version, "1.0.0")
        self.assertEqual(len(self.scanner._probes), 1)

    def test_scan_checks_trigger(self):
        definition = {
            "name": "contains_check",
            "probes": [
                {
                    "input": "Say hello world",
                    "checks": [
                        {
                            "type": "contains",
                            "value": "hello",
                            "severity": "low",
                            "confidence": 0.8,
                        },
                    ],
                },
            ],
        }
        self.scanner.load_definition(definition)
        adapter = MockAdapter({"__default__": "hello world"})
        result = self.scanner.scan(None, adapter)
        self.assertGreater(len(result.findings), 0)
        triggered = [f for f in result.findings if "DSL check triggered" in f.title]
        self.assertGreater(len(triggered), 0)

    def test_scan_no_checks_triggered(self):
        definition = {
            "name": "no_match",
            "probes": [
                {
                    "input": "Say goodbye",
                    "checks": [
                        {
                            "type": "contains",
                            "value": "hello",
                            "severity": "low",
                            "confidence": 0.8,
                        },
                    ],
                },
            ],
        }
        self.scanner.load_definition(definition)
        adapter = MockAdapter({"__default__": "goodbye world"})
        result = self.scanner.scan(None, adapter)
        self.assertGreater(len(result.findings), 0)
        info = [f for f in result.findings if "no checks triggered" in f.title]
        self.assertGreater(len(info), 0)

    def test_load_dsl_scanner_yaml(self):
        import yaml as yaml_lib

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_scanner.yaml"
            definition = {
                "name": "yaml_scanner",
                "description": "Loaded from YAML",
                "probes": [
                    {
                        "input": "test",
                        "checks": [
                            {
                                "type": "contains",
                                "value": "test",
                                "severity": "info",
                                "confidence": 0.5,
                            },
                        ],
                    },
                ],
            }
            with open(path, "w") as f:
                yaml_lib.dump(definition, f)

            from community_ai_audit.plugins.scanners.dsl import load_dsl_scanner

            scanner = load_dsl_scanner(str(path))
            self.assertEqual(scanner.name, "yaml_scanner")

    def test_discover_dsl_scanners(self):
        import yaml as yaml_lib

        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            for fname, name in [
                ("scan_a.yaml", "scanner_a"),
                ("scan_b.yml", "scanner_b"),
            ]:
                with open(d / fname, "w") as f:
                    yaml_lib.dump({"name": name, "probes": []}, f)

            from community_ai_audit.plugins.scanners.dsl import discover_dsl_scanners

            scanners = discover_dsl_scanners(str(d))
            self.assertEqual(len(scanners), 2)
            names = {s.name for s in scanners}
            self.assertEqual(names, {"scanner_a", "scanner_b"})


if __name__ == "__main__":
    unittest.main()
