"""Unit tests for core orchestrator and registry smoke behavior."""

import unittest


class TestAuditOrchestrator(unittest.TestCase):
    def test_init(self):
        from community_ai_audit.core.audit import AuditEngine
        engine = AuditEngine(discovery_on_init=False)
        self.assertIsNotNone(engine.config)

    def test_registry_has_plugins(self):
        from community_ai_audit.core.registry import adapters, connectors, plugins
        adapters.discover()
        connectors.discover()
        plugins.discover()
        self.assertIn("huggingface", adapters.list_available())
        self.assertIn("splunk", connectors.list_available())
        self.assertIn("backdoor", plugins.list_scanners())

    def test_auto_detect_provider(self):
        from community_ai_audit.core.audit import AuditEngine
        engine = AuditEngine(discovery_on_init=False)
        self.assertEqual(engine._auto_detect_provider("gpt-4o"), "openai")
        self.assertEqual(engine._auto_detect_provider("claude-3"), "anthropic")


if __name__ == "__main__":
    unittest.main()