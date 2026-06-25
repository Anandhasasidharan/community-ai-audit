"""System tests for CLI UI: argument parsing, ui module, and subprocess invocation."""

import unittest
import subprocess
import sys
import json
import io
import os
from unittest import mock


# ─────────────────────────────────────────────────────────────
# ui.py module tests
# ─────────────────────────────────────────────────────────────

class TestUIModule(unittest.TestCase):
    """Verify the ui.py module functions work correctly."""

    def setUp(self):
        from community_ai_audit.cli import ui
        self.ui = ui

    def test_import(self):
        self.assertTrue(hasattr(self.ui, 'print_banner'))
        self.assertTrue(hasattr(self.ui, 'install_traceback_handler'))

    def test_score_color(self):
        self.assertEqual(self.ui.score_color(95), "green")
        self.assertEqual(self.ui.score_color(80), "cyan")
        self.assertEqual(self.ui.score_color(70), "yellow")
        self.assertEqual(self.ui.score_color(50), "orange3")
        self.assertEqual(self.ui.score_color(30), "red")

    def test_score_emoji(self):
        self.assertEqual(self.ui.score_emoji(95), "🟢")
        self.assertEqual(self.ui.score_emoji(75), "🟡")
        self.assertEqual(self.ui.score_emoji(35), "🔴")

    def test_rating_label(self):
        self.assertEqual(self.ui.rating_label(95), "Excellent")
        self.assertEqual(self.ui.rating_label(85), "Good")
        self.assertEqual(self.ui.rating_label(75), "Fair")
        self.assertEqual(self.ui.rating_label(65), "Poor")
        self.assertEqual(self.ui.rating_label(25), "Critical")

    def test_header_works(self):
        self.ui.header("Test Header")

    def test_info_warning_error_success(self):
        self.ui.info("info msg")
        self.ui.warning("warn msg")
        self.ui.error("err msg")
        self.ui.success("ok msg")

    def test_divider(self):
        self.ui.divider()

    def test_print_json_with_dict(self):
        out = io.StringIO()
        with mock.patch('sys.stdout', out):
            self.ui.print_json({"a": 1, "b": [2, 3]})
        output = out.getvalue()
        self.assertTrue(len(output) > 0)
        self.assertIn("a", output)

    def test_print_json_with_list(self):
        out = io.StringIO()
        with mock.patch('sys.stdout', out):
            self.ui.print_json([{"x": 1}])
        output = out.getvalue()
        self.assertIn("x", output)

    def test_print_json_invalid(self):
        out = io.StringIO()
        with mock.patch('sys.stdout', out):
            self.ui.print_json({"a": object()})
        output = out.getvalue()
        self.assertIn("a", output)

    def test_confirm_action_default_no(self):
        with mock.patch('builtins.input', return_value=''):
            result = self.ui.confirm_action("Proceed?")
        self.assertFalse(result)

    def test_confirm_action_yes(self):
        with mock.patch('builtins.input', return_value='y'):
            result = self.ui.confirm_action("Proceed?")
        self.assertTrue(result)

    def test_confirm_action_no(self):
        with mock.patch('builtins.input', return_value='n'):
            result = self.ui.confirm_action("Proceed?")
        self.assertFalse(result)


class TestUIRichFallback(unittest.TestCase):
    """Verify fallback when Rich is not installed."""

    def test_fallback_import(self):
        import importlib
        from community_ai_audit.cli import ui

        old_modules = {}
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith('rich') or mod_name == 'rich':
                old_modules[mod_name] = sys.modules[mod_name]
                sys.modules[mod_name] = None  # type: ignore[assignment]

        try:
            importlib.reload(ui)
            self.assertFalse(ui._RICH)

            out = io.StringIO()
            with mock.patch('sys.stdout', out):
                ui.header("Fallback")
                ui.info("fallback info")
                ui.warning("fallback warn")
                ui.error("fallback err")
                ui.success("fallback ok")
                ui.divider()
                ui.print_json({"k": "v"})

            output = out.getvalue()
            self.assertIn("Fallback", output)
            self.assertIn("fallback info", output)
            self.assertIn("OK", output)
        finally:
            for mod_name in old_modules:
                sys.modules[mod_name] = old_modules[mod_name]
            importlib.reload(ui)
            self.assertTrue(ui._RICH)


# ─────────────────────────────────────────────────────────────
# CLI argument parsing tests
# ─────────────────────────────────────────────────────────────

class TestCLIParsing(unittest.TestCase):
    """Verify all 17 CLI commands parse correctly."""

    def setUp(self):
        from community_ai_audit.cli.main import build_parser
        self.parser = build_parser()

    def parse(self, *args):
        return self.parser.parse_args(list(args))

    def test_scan_command(self):
        args = self.parse("scan", "my_model", "--provider", "local")
        self.assertEqual(args.command, "scan")
        self.assertEqual(args.model, "my_model")

    def test_interpret_command(self):
        args = self.parse("interpret", "my_model", "--provider", "local")
        self.assertEqual(args.command, "interpret")

    def test_audit_command(self):
        args = self.parse("audit", "my_model", "--provider", "local")
        self.assertEqual(args.command, "audit")

    def test_discover_command(self):
        args = self.parse("discover")
        self.assertEqual(args.command, "discover")

    def test_eval_command(self):
        args = self.parse("eval", "my_model", "--provider", "openai")
        self.assertEqual(args.command, "eval")

    def test_benchmark_command(self):
        args = self.parse("benchmark", "my_model", "--provider", "local", "--dataset", "truthfulqa")
        self.assertEqual(args.command, "benchmark")

    def test_regression_command(self):
        args = self.parse("regression", "baseline_run.json", "current_run.json")
        self.assertEqual(args.command, "regression")

    def test_datasets_command(self):
        args = self.parse("datasets")
        self.assertEqual(args.command, "datasets")

    def test_schedule_add_command(self):
        args = self.parse("schedule", "add", "daily", "my_model", "--cron", "0 6 * * *", "--provider", "local")
        self.assertEqual(args.command, "schedule")
        self.assertEqual(args.schedule_command, "add")

    def test_schedule_list_command(self):
        args = self.parse("schedule", "list")
        self.assertEqual(args.schedule_command, "list")

    def test_schedule_remove_command(self):
        args = self.parse("schedule", "remove", "daily")
        self.assertEqual(args.schedule_command, "remove")

    def test_schedule_run_command(self):
        args = self.parse("schedule", "run")
        self.assertEqual(args.schedule_command, "run")

    def test_agent_audit_command(self):
        args = self.parse("agent-audit", "--session-file", "s.json", "--agent-id", "my_agent")
        self.assertEqual(args.command, "agent-audit")
        self.assertEqual(args.agent_id, "my_agent")

    def test_agent_trace_replay_command(self):
        args = self.parse("agent-trace", "replay", "s.json")
        self.assertEqual(args.command, "agent-trace")
        self.assertEqual(args.trace_command, "replay")

    def test_agent_trace_export_command(self):
        args = self.parse("agent-trace", "export", "s.json")
        self.assertEqual(args.trace_command, "export")
        self.assertEqual(args.session_file, "s.json")

    def test_agent_dashboard_command(self):
        args = self.parse("agent-dashboard")
        self.assertEqual(args.command, "agent-dashboard")

    def test_agent_monitor_audit_command(self):
        args = self.parse("agent-monitor", "audit", "agent123", "--session-file", "s.json")
        self.assertEqual(args.command, "agent-monitor")
        self.assertEqual(args.monitor_command, "audit")

    def test_agent_monitor_history_command(self):
        args = self.parse("agent-monitor", "history")
        self.assertEqual(args.monitor_command, "history")

    def test_agent_monitor_alerts_command(self):
        args = self.parse("agent-monitor", "alerts")
        self.assertEqual(args.monitor_command, "alerts")

    def test_agent_monitor_drift_command(self):
        args = self.parse("agent-monitor", "drift")
        self.assertEqual(args.monitor_command, "drift")

    def test_redteam_command(self):
        args = self.parse("redteam", "my_model", "--provider", "openai")
        self.assertEqual(args.command, "redteam")

    def test_mechinterp_command(self):
        args = self.parse("mechinterp", "my_model", "--provider", "huggingface")
        self.assertEqual(args.command, "mechinterp")

    def test_alignment_command(self):
        args = self.parse("alignment", "my_model", "--provider", "anthropic")
        self.assertEqual(args.command, "alignment")

    def test_audit_score_command(self):
        args = self.parse("audit-score", "--scan", "scan.json", "--redteam", "red.json")
        self.assertEqual(args.command, "audit-score")

    def test_scan_with_all_flags(self):
        args = self.parse(
            "scan", "model", "--provider", "openai",
            "--scanners", "backdoor", "adversarial",
            "--output", "json", "--save", "out.json",
            "--profile", "deep",
        )
        self.assertEqual(args.scanners, ["backdoor", "adversarial"])
        self.assertEqual(args.output, "json")
        self.assertEqual(args.profile, "deep")

    def test_audit_with_interpreters(self):
        args = self.parse(
            "audit", "model", "--provider", "local",
            "--interpreters", "lime", "integrated-gradients",
        )
        self.assertEqual(args.interpreters, ["lime", "integrated-gradients"])

    def test_format_flag(self):
        args = self.parse("datasets", "--format", "json")
        self.assertEqual(args.format, "json")

    def test_version_flag(self):
        with self.assertRaises(SystemExit):
            self.parse("--version")


# ─────────────────────────────────────────────────────────────
# Subprocess invocation tests
# ─────────────────────────────────────────────────────────────

@unittest.skipIf(sys.platform == "win32", "subprocess tests use posix paths")
class TestCLISubprocess(unittest.TestCase):
    """Invoke the CLI as a subprocess (system-level)."""

    CLI_MODULE = "community_ai_audit.cli.main"

    def test_help_exit_code(self):
        result = subprocess.run(
            [sys.executable, "-m", self.CLI_MODULE, "--help"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage:", result.stdout)

    def test_version_output(self):
        result = subprocess.run(
            [sys.executable, "-m", self.CLI_MODULE, "--version"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)

    def test_discover_runs(self):
        result = subprocess.run(
            [sys.executable, "-m", self.CLI_MODULE, "discover"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("adapters", result.stdout.lower())

    def test_scan_help(self):
        result = subprocess.run(
            [sys.executable, "-m", self.CLI_MODULE, "scan", "--help"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)

    def test_agent_audit_help(self):
        result = subprocess.run(
            [sys.executable, "-m", self.CLI_MODULE, "agent-audit", "--help"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)

    def test_agent_monitor_help(self):
        result = subprocess.run(
            [sys.executable, "-m", self.CLI_MODULE, "agent-monitor", "--help"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)

    def test_redteam_help(self):
        result = subprocess.run(
            [sys.executable, "-m", self.CLI_MODULE, "redteam", "--help"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)

    def test_mechinterp_help(self):
        result = subprocess.run(
            [sys.executable, "-m", self.CLI_MODULE, "mechinterp", "--help"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)

    def test_alignment_help(self):
        result = subprocess.run(
            [sys.executable, "-m", self.CLI_MODULE, "alignment", "--help"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)

    def test_datasets_runs(self):
        result = subprocess.run(
            [sys.executable, "-m", self.CLI_MODULE, "datasets"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)

    def test_schedule_help(self):
        result = subprocess.run(
            [sys.executable, "-m", self.CLI_MODULE, "schedule", "--help"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)

    def test_eval_help(self):
        result = subprocess.run(
            [sys.executable, "-m", self.CLI_MODULE, "eval", "--help"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)

    def test_benchmark_help(self):
        result = subprocess.run(
            [sys.executable, "-m", self.CLI_MODULE, "benchmark", "--help"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)

    def test_regression_help(self):
        result = subprocess.run(
            [sys.executable, "-m", self.CLI_MODULE, "regression", "--help"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)


# ─────────────────────────────────────────────────────────────
# CLI handler integration tests (with mocked engine)
# ─────────────────────────────────────────────────────────────

class FakeArgs:
    """Minimal args object for command handler tests."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockEngine:
    """Minimal mock engine for command handler tests."""

    def __init__(self):
        self.config = {}

    def load_model(self, *a, **kw): pass
    def scan(self, *a, **kw): return []
    def interpret(self, *a, **kw): return []
    def list_capabilities(self): return {"adapters": [], "connectors": [], "scanners": [], "interpreters": [], "reporters": []}
    def audit(self, *a, **kw): return self
    def scan_results(self): return []
    def interpret_results(self): return []
    def to_report_dict(self): return {}


class TestCommandHandlers(unittest.TestCase):
    """Exercise command handlers with mocked dependencies."""

    @classmethod
    def setUpClass(cls):
        from community_ai_audit.cli.main import (
            _cmd_discover, _cmd_scan, _cmd_audit_score, _cmd_datasets,
            _cmd_schedule,
        )
        cls._cmd_discover = _cmd_discover
        cls._cmd_scan = _cmd_scan
        cls._cmd_audit_score = _cmd_audit_score
        cls._cmd_datasets = _cmd_datasets
        cls._cmd_schedule = _cmd_schedule

    def test_discover_handler(self):
        engine = MockEngine()
        args = FakeArgs(format="text")
        result = TestCommandHandlers._cmd_discover(engine, args)
        self.assertEqual(result, 0)

    def test_discover_json_format(self):
        engine = MockEngine()
        args = FakeArgs(format="json")
        result = TestCommandHandlers._cmd_discover(engine, args)
        self.assertEqual(result, 0)

    def test_scan_handler(self):
        engine = MockEngine()
        args = FakeArgs(model="test", provider="local", output="json", profile=None,
                        scanners=None, save=None, connectors=None,
                        probe_file=None, api_key_file=None, api_key=None,
                        device=None, config=None,
                        scanner_config=None, report_format="text")
        result = TestCommandHandlers._cmd_scan(engine, args)
        self.assertEqual(result, 0)

    def test_datasets_handler(self):
        args = FakeArgs(format="text")
        result = TestCommandHandlers._cmd_datasets(args)
        self.assertEqual(result, 0)

    def test_datasets_json(self):
        args = FakeArgs(format="json")
        result = TestCommandHandlers._cmd_datasets(args)
        self.assertEqual(result, 0)

    def test_schedule_list_handler(self):
        engine = MockEngine()
        args = FakeArgs(schedule_command="list", name=None, cron=None, model=None,
                        provider=None, scanners=None, interpreters=None, connectors=None,
                        profile=None, output=None)
        result = TestCommandHandlers._cmd_schedule(engine, args)
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
