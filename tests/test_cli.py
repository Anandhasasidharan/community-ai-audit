"""Unit tests for the CLI module."""

import unittest


class TestCLI(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.cli.main import build_parser

        self.parser = build_parser()

    def test_scan_command(self):
        args = self.parser.parse_args(["scan", "my_model.pt", "--provider", "local"])
        self.assertEqual(args.command, "scan")
        self.assertEqual(args.model, "my_model.pt")

    def test_interpret_command(self):
        args = self.parser.parse_args(["interpret", "my_model.pt", "--provider", "local"])
        self.assertEqual(args.command, "interpret")
        self.assertEqual(args.model, "my_model.pt")

    def test_audit_command(self):
        args = self.parser.parse_args(["audit", "my_model.pt", "--provider", "local"])
        self.assertEqual(args.command, "audit")
        self.assertEqual(args.model, "my_model.pt")

    def test_discover_command(self):
        args = self.parser.parse_args(["discover"])
        self.assertEqual(args.command, "discover")

    def test_scan_with_probe_file(self):
        args = self.parser.parse_args(
            [
                "scan",
                "my_model.pt",
                "--provider",
                "local",
                "--probe-file",
                "examples/data/toy_probe.json",
            ]
        )
        self.assertEqual(args.command, "scan")
        self.assertEqual(args.probe_file, "examples/data/toy_probe.json")

    def test_audit_with_profile(self):
        args = self.parser.parse_args(
            ["audit", "my_model.pt", "--provider", "local", "--profile", "deep"]
        )
        self.assertEqual(args.command, "audit")
        self.assertEqual(args.profile, "deep")

    def test_version(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["--version"])


if __name__ == "__main__":
    unittest.main()
