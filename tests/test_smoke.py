"""Smoke tests for importability, discovery, and CLI parsing.
These use stdlib unittest so they can run without pytest.
"""

import unittest


class TestSmoke(unittest.TestCase):
    def test_package_import(self):
        import community_ai_audit

        # Version should be a valid semver string (not hardcoded to avoid CI failures)
        self.assertRegex(community_ai_audit.__version__, r"^\d+\.\d+\.\d+")
        self.assertTrue(hasattr(community_ai_audit, "AuditEngine"))

    def test_registry_discovery(self):
        from community_ai_audit.core.registry import adapters, connectors, plugins

        adapters.discover()
        connectors.discover()
        plugins.discover()
        self.assertGreaterEqual(len(adapters.list_available()), 1)
        self.assertGreaterEqual(len(connectors.list_available()), 1)
        self.assertIn("backdoor", plugins.list_scanners())
        self.assertIn("markdown", plugins.list_reporters())

    def test_cli_parser(self):
        from community_ai_audit.cli.main import build_parser

        parser = build_parser()
        args = parser.parse_args(["discover"])
        self.assertEqual(args.command, "discover")


if __name__ == "__main__":
    unittest.main()
