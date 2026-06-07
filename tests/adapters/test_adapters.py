"""Tests for all built-in model adapters."""

import unittest
from unittest.mock import patch, MagicMock

from community_ai_audit.core.interfaces import ModelAdapter, TextModelAdapter


class TestAdapterBaseInterface(unittest.TestCase):
    def test_model_adapter_abstract_methods(self):
        """ModelAdapter ABC requires connect, disconnect, get_model, predict, get_input_spec, supports_model_type."""
        methods = ["connect", "disconnect", "get_model", "predict", "get_input_spec", "supports_model_type"]
        for m in methods:
            self.assertTrue(
                hasattr(ModelAdapter, m),
                f"ModelAdapter missing abstract method: {m}",
            )

    def test_text_model_adapter_extra_methods(self):
        """TextModelAdapter additionally requires tokenize, generate, get_logits, get_attention_weights."""
        methods = ["tokenize", "generate", "get_logits", "get_attention_weights"]
        for m in methods:
            self.assertTrue(
                hasattr(TextModelAdapter, m),
                f"TextModelAdapter missing abstract method: {m}",
            )


class TestLocalAdapter(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.adapters.local_adapter import LocalAdapter

        self.adapter = LocalAdapter()

    def test_name_and_provider(self):
        self.assertEqual(self.adapter.name, "local")
        self.assertEqual(self.adapter.provider, "local")

    def test_connect_import_error(self):
        with patch("community_ai_audit.adapters.local_adapter.safe_import", return_value=None):
            with self.assertRaises(ImportError):
                self.adapter.connect({})

    def test_connect_success(self):
        with patch("community_ai_audit.adapters.local_adapter.safe_import") as mock_import:
            mock_torch = MagicMock()
            mock_import.return_value = mock_torch
            self.adapter.connect({"device": "cpu"})
            self.assertEqual(self.adapter._device, "cpu")

    def test_disconnect_cleanup(self):
        self.adapter._model = MagicMock()
        self.adapter.disconnect()
        self.assertIsNone(self.adapter._model)

    def test_get_model_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.adapter.get_model("/nonexistent/path/to/model.pt")

    def test_get_model_unsupported_extension(self):
        from pathlib import Path
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "is_dir", return_value=False):
                with patch.object(Path, "suffix", ".xyz"):
                    with self.assertRaises(ValueError):
                        self.adapter.get_model("model.xyz")

    def test_resolve_device_auto(self):
        device = self.adapter._resolve_device("auto")
        self.assertIn(device, ["cpu", "cuda", "mps"])

    def test_resolve_device_cpu(self):
        device = self.adapter._resolve_device("cpu")
        self.assertEqual(device, "cpu")

    def test_get_config_schema(self):
        from community_ai_audit.adapters.local_adapter import LocalAdapter
        schema = LocalAdapter.get_config_schema()
        self.assertIsInstance(schema, dict)


class TestHuggingFaceAdapter(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.adapters.huggingface_adapter import HuggingFaceAdapter

        self.adapter = HuggingFaceAdapter()

    def test_name_and_provider(self):
        self.assertEqual(self.adapter.name, "huggingface")
        self.assertEqual(self.adapter.provider, "huggingface")

    def test_connect_calls_lazy_import(self):
        with patch("community_ai_audit.adapters.huggingface_adapter._lazy_import") as mock_lazy:
            self.adapter.connect({"device": "cpu"})
            mock_lazy.assert_called_once()

    def test_disconnect_cleanup(self):
        self.adapter._model = MagicMock()
        self.adapter.disconnect()
        self.assertIsNone(self.adapter._model)
        self.assertIsNone(self.adapter._tokenizer)

    def test_supported_types(self):
        from community_ai_audit.core.interfaces import ModelType
        expected = {ModelType.TEXT, ModelType.IMAGE, ModelType.MULTIMODAL, ModelType.EMBEDDING}
        self.assertEqual(set(self.adapter.supported_types), expected)

    def test_get_config_schema(self):
        from community_ai_audit.adapters.huggingface_adapter import HuggingFaceAdapter
        schema = HuggingFaceAdapter.get_config_schema()
        self.assertIsInstance(schema, dict)

    @patch("community_ai_audit.adapters.huggingface_adapter.safe_import", return_value=None)
    def test_get_model_without_transformers(self, _mock):
        self.adapter._device = "cpu"
        with self.assertRaises(ImportError):
            self.adapter.get_model("dummy")


class _FakeOpenAI:
    OpenAI = MagicMock()


class TestOpenAIAdapter(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.adapters.openai_adapter import OpenAIAdapter

        self.adapter = OpenAIAdapter()

    def test_name_and_provider(self):
        self.assertEqual(self.adapter.name, "openai")
        self.assertEqual(self.adapter.provider, "openai")

    @patch.dict("sys.modules", {"openai": _FakeOpenAI})
    def test_connect_no_api_key(self):
        with self.assertRaises(ValueError):
            self.adapter.connect({})

    @patch.dict("sys.modules", {"openai": _FakeOpenAI})
    def test_connect_with_api_key(self):
        self.adapter.connect({"api_key": "sk-test"})
        self.assertIsNotNone(self.adapter._client)

    def test_disconnect(self):
        self.adapter.disconnect()
        self.assertIsNone(self.adapter._client)

    def test_supports_model_type_text(self):
        from community_ai_audit.core.interfaces import ModelType
        self.assertTrue(self.adapter.supports_model_type(ModelType.TEXT))
        self.assertFalse(self.adapter.supports_model_type(ModelType.IMAGE))

    def test_get_config_schema(self):
        from community_ai_audit.adapters.openai_adapter import OpenAIAdapter
        schema = OpenAIAdapter.get_config_schema()
        self.assertIsInstance(schema, dict)


class _FakeAnthropic:
    __version__ = "0.30.0"
    Anthropic = MagicMock()


class TestAnthropicAdapter(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.adapters.anthropic_adapter import AnthropicAdapter

        self.adapter = AnthropicAdapter()

    def test_name_and_provider(self):
        self.assertEqual(self.adapter.name, "anthropic")
        self.assertEqual(self.adapter.provider, "anthropic")

    @patch("community_ai_audit.adapters.anthropic_adapter.safe_import", return_value=_FakeAnthropic)
    def test_connect_no_api_key(self, mock_import):
        with self.assertRaises(ValueError):
            self.adapter.connect({})

    @patch.dict("sys.modules", {"anthropic": _FakeAnthropic})
    @patch("community_ai_audit.adapters.anthropic_adapter.safe_import", return_value=_FakeAnthropic)
    def test_connect_with_api_key(self, mock_import):
        self.adapter.connect({"api_key": "sk-ant-test"})
        self.assertIsNotNone(self.adapter._client)

    def test_disconnect(self):
        self.adapter.disconnect()
        self.assertIsNone(self.adapter._client)

    def test_get_config_schema(self):
        from community_ai_audit.adapters.anthropic_adapter import AnthropicAdapter
        schema = AnthropicAdapter.get_config_schema()
        self.assertIsInstance(schema, dict)


class TestAWSBedrockAdapter(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.adapters.aws_bedrock_adapter import AWSBedrockAdapter

        self.adapter = AWSBedrockAdapter()

    def test_name_and_provider(self):
        self.assertEqual(self.adapter.name, "aws_bedrock")
        self.assertEqual(self.adapter.provider, "aws")

    @patch("community_ai_audit.adapters.aws_bedrock_adapter.safe_import", return_value=MagicMock())
    def test_connect_with_region(self, mock_import):
        mock_boto3 = MagicMock()
        mock_boto3.Session.return_value.client.return_value = MagicMock()
        mock_import.return_value = mock_boto3
        self.adapter.connect({"region_name": "us-east-1"})
        self.assertIsNotNone(self.adapter._client)

    @patch("community_ai_audit.adapters.aws_bedrock_adapter.safe_import")
    def test_connect_no_boto3(self, mock_import):
        mock_import.return_value = None
        with self.assertRaises(ImportError):
            self.adapter.connect({})

    def test_disconnect(self):
        self.adapter.disconnect()
        self.assertIsNone(self.adapter._client)

    def test_get_config_schema(self):
        from community_ai_audit.adapters.aws_bedrock_adapter import AWSBedrockAdapter
        schema = AWSBedrockAdapter.get_config_schema()
        self.assertIsInstance(schema, dict)


class TestOllamaAdapter(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.adapters.ollama_adapter import OllamaAdapter

        self.adapter = OllamaAdapter()

    def test_name_and_provider(self):
        self.assertEqual(self.adapter.name, "ollama")
        self.assertEqual(self.adapter.provider, "ollama")

    @patch("requests.get")
    def test_connect_sets_base_url(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        self.adapter.connect({"base_url": "http://localhost:11434"})
        self.assertEqual(self.adapter._base_url, "http://localhost:11434")

    @patch("requests.get")
    def test_connect_default_url(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        self.adapter.connect({})
        self.assertEqual(self.adapter._base_url, "http://localhost:11434")

    def test_disconnect(self):
        self.adapter.disconnect()
        self.assertIsNone(self.adapter._client)

    def test_supports_model_type_text(self):
        from community_ai_audit.core.interfaces import ModelType
        self.assertTrue(self.adapter.supports_model_type(ModelType.TEXT))

    def test_get_config_schema(self):
        from community_ai_audit.adapters.ollama_adapter import OllamaAdapter
        schema = OllamaAdapter.get_config_schema()
        self.assertIsInstance(schema, dict)


class TestRegistryResolution(unittest.TestCase):
    def test_all_adapters_discoverable(self):
        from community_ai_audit.core.registry import adapters
        adapters.discover()
        available = adapters.list_available()
        for name in ("local", "huggingface", "openai", "anthropic", "aws_bedrock", "ollama"):
            self.assertIn(name, available, f"Adapter {name} not found in registry")

    def test_adapter_get_returns_instance(self):
        from community_ai_audit.core.interfaces import ModelAdapter
        from community_ai_audit.core.registry import adapters
        adapters.discover()
        for name in adapters.list_available():
            inst = adapters.get(name)
            self.assertIsInstance(inst, ModelAdapter, f"{name} is not a ModelAdapter instance")


if __name__ == "__main__":
    unittest.main()
