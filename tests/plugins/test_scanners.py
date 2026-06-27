"""Tests for built-in scanner plugins with mock torch models."""

import unittest
from unittest.mock import MagicMock, patch

try:
    import torch
    import torch.nn as nn

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    torch = None
    nn = None


from community_ai_audit.adapters.base import get_model_device

skip_if_no_torch = unittest.skipIf(not HAS_TORCH, "torch not installed")


class _DummyAdapter:
    name = "local"
    provider = "local"

    def predict(self, x):
        return {"outputs": [0.5]}

    def get_input_spec(self):
        return {"type": "numeric"}

    def supports_model_type(self, t):
        return True


@skip_if_no_torch
class TestBackdoorScanner(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.plugins.scanners.backdoor import BackdoorScanner

        self.scanner = BackdoorScanner()

    def test_name_and_version(self):
        self.assertEqual(self.scanner.name, "backdoor")
        self.assertEqual(self.scanner.version, "0.2.0")

    def test_scan_non_whitebox_model_returns_info_finding(self):
        model = "not-a-model"
        adapter = _DummyAdapter()
        result = self.scanner.scan(model, adapter)
        self.assertEqual(len(result.findings), 1)
        self.assertIn("limited", result.findings[0].title.lower())

    def test_scan_with_mock_model_produces_findings(self):
        class _DummyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 5)
                self.config = MagicMock()
                self.config.vocab_size = 100

            def forward(self, x):
                return self.fc(x.float() if x.dtype == torch.long else x)

        model = _DummyModel()
        adapter = _DummyAdapter()
        result = self.scanner.scan(model, adapter, config={"sample_size": 32, "num_clusters": 3})
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result.findings), 1)

    def test_scan_handles_activation_exception(self):
        class _DummyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 5)
                self.config = MagicMock()
                self.config.vocab_size = 100

            def forward(self, x):
                return self.fc(x.float() if x.dtype == torch.long else x)

        model = _DummyModel()
        adapter = _DummyAdapter()
        result = self.scanner.scan(model, adapter, config={"input_shape": [16]})
        self.assertIsNotNone(result)

    def test_scan_no_activations_fallback(self):
        class _DummyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 5)
                self.config = MagicMock()
                self.config.vocab_size = 100

            def forward(self, x):
                return self.fc(x.float() if x.dtype == torch.long else x)

        model = _DummyModel()
        adapter = _DummyAdapter()
        with patch.object(self.scanner, "_extract_activations", return_value={}):
            result = self.scanner.scan(model, adapter)
            self.assertEqual(len(result.findings), 1)
            self.assertIn("No activations", result.findings[0].title)

    def test_get_device(self):
        class _DummyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 5)
                self.config = MagicMock()
                self.config.vocab_size = 100

            def forward(self, x):
                return self.fc(x.float() if x.dtype == torch.long else x)

        model = _DummyModel()
        device = get_model_device(model)
        self.assertEqual(device, torch.device("cpu"))

    def test_flatten_data_with_tensor(self):
        t = torch.tensor([[1.0, 2.0], [3.0, 4.0]])
        flat = self.scanner._flatten_data(t)
        self.assertEqual(flat, [[1.0, 2.0], [3.0, 4.0]])

    def test_flatten_data_empty(self):
        self.assertEqual(self.scanner._flatten_data([]), [])

    def test_run_clustering_returns_outliers(self):
        import numpy as np

        vectors = np.random.randn(100, 5).tolist()
        scores = self.scanner._run_clustering(
            vectors, n_clusters=5, threshold=0.85, sample_size=100
        )
        self.assertIsInstance(scores, list)

    def test_build_probe_batch_text_model(self):
        class _DummyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 5)
                self.config = MagicMock()
                self.config.vocab_size = 100

            def forward(self, x):
                return self.fc(x.float() if x.dtype == torch.long else x)

        model = _DummyModel()
        device = torch.device("cpu")
        batch = self.scanner._build_probe_batch(
            model, {"sample_size": 16, "input_shape": [10]}, device=device
        )
        self.assertIsNotNone(batch)
        self.assertEqual(batch.shape[0], 16)
        self.assertEqual(batch.dtype, torch.long)

    def test_build_probe_batch_with_input_shape(self):
        class _DummyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 5)
                self.config = MagicMock()
                self.config.vocab_size = 100

            def forward(self, x):
                return self.fc(x.float() if x.dtype == torch.long else x)

        model = _DummyModel()
        device = torch.device("cpu")
        batch = self.scanner._build_probe_batch(
            model, {"input_shape": [10], "sample_size": 8}, device=device
        )
        self.assertIsNotNone(batch)
        self.assertEqual(batch.shape[0], 8)


@skip_if_no_torch
class TestAdversarialScanner(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.plugins.scanners.adversarial import AdversarialScanner

        self.scanner = AdversarialScanner()

    def test_name_and_version(self):
        self.assertEqual(self.scanner.name, "adversarial")
        self.assertEqual(self.scanner.version, "0.2.0")

    def test_scan_blackbox_adapter_returns_limited_finding(self):
        class _DummyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 5)
                self.config = MagicMock()
                self.config.vocab_size = 100

            def forward(self, x):
                return self.fc(x.float() if x.dtype == torch.long else x)

        model = _DummyModel()
        adapter = MagicMock()
        adapter.provider = "openai"
        result = self.scanner.scan(model, adapter)
        self.assertEqual(len(result.findings), 1)
        self.assertIn("limited", result.findings[0].title.lower())

    def test_scan_text_model_returns_limited_finding(self):
        class _DummyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 5)
                self.config = MagicMock()
                self.config.vocab_size = 100

            def forward(self, x):
                return self.fc(x.float() if x.dtype == torch.long else x)

        model = _DummyModel()
        adapter = _DummyAdapter()
        result = self.scanner.scan(model, adapter)
        self.assertIn("limited", result.findings[0].title.lower())

    def test_scan_whitebox_non_text_model_succeeds(self):
        class _DummyNonTextModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 5)
                self.config = object()

            def forward(self, x):
                return self.fc(x)

        model = _DummyNonTextModel()
        adapter = _DummyAdapter()
        result = self.scanner.scan(
            model,
            adapter,
            config={
                "num_samples": 4,
                "epsilon": 0.05,
                "alpha": 0.01,
                "pgd_steps": 3,
                "input_shape": [10],
            },
        )
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result.findings), 1)

    def test_supports_gradients(self):
        class _DummyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 5)
                self.config = MagicMock()
                self.config.vocab_size = 100

            def forward(self, x):
                return self.fc(x.float() if x.dtype == torch.long else x)

        model = _DummyModel()
        self.assertTrue(self.scanner._supports_gradients(_DummyAdapter(), model))

        remote_adapter = MagicMock()
        remote_adapter.provider = "openai"
        self.assertFalse(self.scanner._supports_gradients(remote_adapter, model))

    def test_severity_from_success(self):
        from community_ai_audit.core.interfaces import Severity
        from community_ai_audit.adapters.base import severity_from_threshold

        self.assertEqual(
            severity_from_threshold(
                0.9, None, {"critical": 0.8, "high": 0.6, "medium": 0.3, "low": 0.1}
            ),
            Severity.CRITICAL,
        )
        self.assertEqual(
            severity_from_threshold(
                0.7, None, {"critical": 0.8, "high": 0.6, "medium": 0.3, "low": 0.1}
            ),
            Severity.HIGH,
        )
        self.assertEqual(
            severity_from_threshold(
                0.4, None, {"critical": 0.8, "high": 0.6, "medium": 0.3, "low": 0.1}
            ),
            Severity.MEDIUM,
        )
        self.assertEqual(
            severity_from_threshold(
                0.2, None, {"critical": 0.8, "high": 0.6, "medium": 0.3, "low": 0.1}
            ),
            Severity.LOW,
        )
        self.assertEqual(
            severity_from_threshold(
                0.05, None, {"critical": 0.8, "high": 0.6, "medium": 0.3, "low": 0.1}
            ),
            Severity.INFO,
        )

    def test_fgsm_runs(self):
        class _DummyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 5)
                self.config = MagicMock()
                self.config.vocab_size = 100

            def forward(self, x):
                return self.fc(x.float() if x.dtype == torch.long else x)

        model = _DummyModel()
        x = torch.randn(2, 10)
        y = torch.tensor([0, 1])
        adv = self.scanner._fgsm(model, x, y, epsilon=0.1)
        self.assertEqual(adv.shape, x.shape)

    def test_pgd_runs(self):
        class _DummyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 5)
                self.config = MagicMock()
                self.config.vocab_size = 100

            def forward(self, x):
                return self.fc(x.float() if x.dtype == torch.long else x)

        model = _DummyModel()
        x = torch.randn(2, 10)
        y = torch.tensor([0, 1])
        adv = self.scanner._pgd(model, x, y, epsilon=0.1, alpha=0.01, steps=3)
        self.assertEqual(adv.shape, x.shape)


if __name__ == "__main__":
    unittest.main()
