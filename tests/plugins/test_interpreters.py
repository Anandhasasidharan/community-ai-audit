"""Tests for built-in interpreter plugins with mock torch models."""

import unittest
from unittest.mock import MagicMock, patch

import torch
import torch.nn as nn


class _DummyModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(10, 2)
        self.config = MagicMock()
        self.config.vocab_size = 100

    def forward(self, x):
        return self.fc(x.float() if x.dtype == torch.long else x)


class _DummyAdapter:
    name = "local"
    provider = "local"

    def predict(self, x):
        return {"outputs": [0.5]}

    def get_input_spec(self):
        return {"type": "numeric"}

    def supports_model_type(self, t):
        return True


class TestIntegratedGradientsInterpreter(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.plugins.interpreters.integrated_gradients import (
            IntegratedGradientsInterpreter,
        )

        self.interpreter = IntegratedGradientsInterpreter()

    def test_name_and_version(self):
        self.assertEqual(self.interpreter.name, "integrated-gradients")
        self.assertEqual(self.interpreter.version, "0.2.0")

    def test_interpret_blackbox_adapter_returns_error(self):
        model = _DummyModel()
        adapter = MagicMock()
        adapter.provider = "openai"
        result = self.interpreter.interpret(model, adapter, inputs=[0.1, 0.2])
        self.assertIsNotNone(result.error)

    def test_interpret_text_model_returns_error(self):
        model = _DummyModel()
        adapter = _DummyAdapter()
        result = self.interpreter.interpret(model, adapter, inputs=[0.1, 0.2])
        self.assertIsNotNone(result.error)
        self.assertIn("not supported", result.error)

    def test_interpret_non_text_model_succeeds(self):
        class _DummyNonTextModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 2)
                self.config = object()

            def forward(self, x):
                return self.fc(x)

        model = _DummyNonTextModel()
        adapter = _DummyAdapter()
        result = self.interpreter.interpret(
            model, adapter, inputs=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            config={"steps": 10},
        )
        self.assertIsNone(result.error)
        self.assertIn("integrated_gradients", result.attributions)
        self.assertIsNotNone(result.summary)

    def test_interpret_with_target(self):
        class _DummyNonTextModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 2)
                self.config = object()

            def forward(self, x):
                return self.fc(x)

        model = _DummyNonTextModel()
        adapter = _DummyAdapter()
        result = self.interpreter.interpret(
            model, adapter, inputs=[0.1] * 10, target=0, config={"steps": 5},
        )
        self.assertIsNone(result.error)
        self.assertIn("target_index", result.metadata)
        self.assertEqual(result.metadata["target_index"], 0)

    def test_unsupported_input_format(self):
        class _ModelWithParams:
            config = object()
            def parameters(self):
                return iter([])

        model = _ModelWithParams()
        adapter = _DummyAdapter()
        result = self.interpreter.interpret(model, adapter, inputs=None)
        self.assertIsNotNone(result.error)
        self.assertIn("Unsupported input format", result.error)

    def test_summarize(self):
        attr = torch.tensor([[0.1, 0.5, 0.3]])
        summary = self.interpreter._summarize(attr)
        self.assertIn("mean", summary.lower())

    def test_can_compute_gradients(self):
        model = _DummyModel()
        self.assertTrue(self.interpreter._can_compute_gradients(_DummyAdapter(), model))
        remote = MagicMock()
        remote.provider = "anthropic"
        self.assertFalse(self.interpreter._can_compute_gradients(remote, model))

    def test_forward_logits(self):
        model = _DummyModel()
        x = torch.randn(1, 10)
        logits = self.interpreter._forward_logits(model, x)
        self.assertEqual(logits.shape, (1, 2))

    def test_forward_logits_tuple_output(self):
        class _TupleModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 2)

            def forward(self, x):
                return (self.fc(x),)

        model = _TupleModel()
        x = torch.randn(1, 10)
        logits = self.interpreter._forward_logits(model, x)
        self.assertEqual(logits.shape, (1, 2))

    def test_integrated_gradients_computation(self):
        class _SimpleModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(4, 2)

            def forward(self, x):
                return self.fc(x)

        model = _SimpleModel()
        x = torch.tensor([[1.0, 2.0, 3.0, 4.0]])
        baseline = torch.zeros_like(x)
        attr = self.interpreter._integrated_gradients(model, x, baseline, target_idx=0, steps=10)
        self.assertEqual(attr.shape, x.shape)

    def test_to_tensor_input_variants(self):
        device = torch.device("cpu")
        t = self.interpreter._to_tensor_input([1.0, 2.0, 3.0], device)
        self.assertIsNotNone(t)
        self.assertEqual(t.dtype, torch.float32)

        t2 = self.interpreter._to_tensor_input(torch.tensor([1.0, 2.0]), device)
        self.assertIsNotNone(t2)

        t3 = self.interpreter._to_tensor_input({"tensor": [1.0, 2.0]}, device)
        self.assertIsNotNone(t3)


class TestLIMEInterpreter(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.plugins.interpreters.lime import LIMEInterpreter

        self.interpreter = LIMEInterpreter()

    def test_name_and_version(self):
        self.assertEqual(self.interpreter.name, "lime")
        self.assertEqual(self.interpreter.version, "0.1.0")

    def test_interpret_non_text_model_returns_error(self):
        class _NonTextModel:
            config = object()

        model = _NonTextModel()
        adapter = _DummyAdapter()
        result = self.interpreter.interpret(model, adapter, inputs="test input")
        self.assertIsNotNone(result.error)
        self.assertIn("text model", result.error.lower())

    def test_interpret_text_model_without_lime_installed(self):
        model = _DummyModel()
        adapter = _DummyAdapter()
        with patch("community_ai_audit.plugins.interpreters.lime.safe_import", return_value=None):
            result = self.interpreter.interpret(model, adapter, inputs="test input")
            self.assertIsNotNone(result.error)
            self.assertIn("lime", result.error.lower())

    def test_to_tensor_input_dict_form(self):
        from community_ai_audit.plugins.interpreters.integrated_gradients import (
            IntegratedGradientsInterpreter,
        )

        interp = IntegratedGradientsInterpreter()
        device = torch.device("cpu")
        t = interp._to_tensor_input({"input": [0.1, 0.2]}, device)
        self.assertIsNotNone(t)
        self.assertEqual(t.dtype, torch.float32)


class TestInterpretationResult(unittest.TestCase):
    def test_to_dict(self):
        from community_ai_audit.core.interfaces import InterpretationResult

        r = InterpretationResult(
            interpreter_name="test",
            interpreter_version="1.0",
            attributions={"feature_1": 0.5},
        )
        d = r.to_dict()
        self.assertEqual(d["interpreter"], "test")
        self.assertEqual(d["attributions"]["feature_1"], 0.5)

    def test_to_dict_with_error(self):
        from community_ai_audit.core.interfaces import InterpretationResult

        r = InterpretationResult(
            interpreter_name="test", interpreter_version="1.0", error="something failed"
        )
        d = r.to_dict()
        self.assertEqual(d["error"], "something failed")


if __name__ == "__main__":
    unittest.main()
