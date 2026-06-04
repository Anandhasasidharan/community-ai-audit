"""Unit tests for Registry discovery, registration, and lookup."""

import unittest
from unittest.mock import patch, MagicMock

from community_ai_audit.core.registry import Registry, AdapterRegistry, ConnectorRegistry


class FakePlugin:
    name = "test-plugin"


class MockModule:
    FakePluginClass = type("FakePluginClass", (FakePlugin,), {})  # No-op class inherits FakePlugin


class TestRegistry(unittest.TestCase):
    def test_basic_register_and_get(self):
        reg = Registry()
        reg.register("my-plugin", FakePlugin)
        self.assertIn("my-plugin", reg.list_available())
        instance = reg.get("my-plugin")
        self.assertIsInstance(instance, FakePlugin)

    def test_get_raises_on_missing(self):
        reg = Registry()
        with self.assertRaises(KeyError):
            reg.get("missing")

    def test_discover_builtins(self):
        reg = AdapterRegistry()
        reg.discover()
        self.assertTrue(len(reg.list_available()) > 0)

    @patch('community_ai_audit.core.registry.entry_points')
    def test_entry_point_discovery(self, mock_entry_points):
        """Simulate plugin loaded via entry points."""
        from community_ai_audit.core.interfaces import SIEMConnector

        class MockConnector(SIEMConnector):
            name = "mock-connector"

            def connect(self, config):
                pass
            def disconnect(self):
                pass
            def send_event(self, event, event_type="audit"):
                return True
            def send_batch(self, events, event_type="audit"):
                return {"success": 0, "failed": 0}
            def query(self, query, time_range=None):
                return []
            @classmethod
            def get_config_schema(cls):
                return {}

        mock_ep = MagicMock()
        mock_ep.name = "mock-connector"
        mock_ep.load.return_value = MockConnector
        # entry_points(group=...) returns an iterable of entry points
        mock_entry_points.return_value = [mock_ep]

        reg = ConnectorRegistry()
        reg._discover_entry_points()
        self.assertIn("mock-connector", reg.list_available())

    def test_adapter_registry_model_type_filter(self):
        reg = AdapterRegistry()
        reg.discover()
        # Ensure HuggingFace adapter is discovered
        self.assertIn("huggingface", reg.list_available())

    def test_connector_registry_siem_filter(self):
        reg = ConnectorRegistry()
        reg.discover()
        names = reg.list_available()
        self.assertIn("splunk", names)
        self.assertIn("elastic", names)
        self.assertIn("datadog", names)
        self.assertIn("sentinel", names)

    def test_duplicate_register_skipped_by_default(self):
        reg = Registry()
        reg.register("dup", FakePlugin)
        reg.register("dup", FakePlugin)
        self.assertEqual(reg.list_available().count("dup"), 1)

    def test_register_override(self):
        reg = Registry()
        reg.register("dup", FakePlugin)
        new_cls = type("NewPlugin", (FakePlugin,), {})
        reg.register("dup", new_cls, replace=True)
        self.assertEqual(reg._plugins["dup"], new_cls)

    def test_list_with_info(self):
        reg = Registry()
        reg.register("info", FakePlugin)
        info = reg.list_with_info()
        self.assertEqual(len(info), 1)
        self.assertEqual(info[0]["name"], "info")
        self.assertEqual(info[0]["class"], "FakePlugin")


if __name__ == "__main__":
    unittest.main()
