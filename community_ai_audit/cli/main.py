"""
Command-line interface for the community AI security audit tool.
Uses the plug-and-play AuditEngine under the hood.
"""

import argparse
import sys
import json
import os
import time
import logging
from typing import Any, List, Optional

from community_ai_audit.cli import ui

from community_ai_audit.core.rbac import PermissionError as RBACPermError

# ─────────────────────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────────────────────


def _setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ─────────────────────────────────────────────────────────────
# Argument parser
# ─────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="community-ai-audit",
        description="Community-driven AI security audit tool — plug-and-play with any model, any SIEM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  community-ai-audit audit meta-llama/Llama-3-8B-Instruct --provider huggingface
  community-ai-audit scan model.pt --provider local --scanners backdoor adversarial
  community-ai-audit interpret model.pt --provider local --interpreters integrated-gradients
  
Environment:
  COMMUNITY_AI_AUDIT_CONFIG      Path to YAML config override.
  COMMUNITY_AI_AUDIT_PLUGIN_PATH Colon-separated plugin directories.
  COMMUNITY_AI_AUDIT_LOG_LEVEL   One of: DEBUG, INFO, WARNING, ERROR.
""",
    )
    parser.add_argument("--version", action="version", version="community-ai-audit 0.1.0")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output (DEBUG)")
    parser.add_argument("--config", help="Path to YAML config file")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── scan command ────────────────────────────────────────────
    scan_parser = subparsers.add_parser("scan", help="Run vulnerability scanners on a model")
    scan_parser.add_argument("model", help="Model identifier (local path, HF repo, API model name)")
    scan_parser.add_argument(
        "--provider",
        "-p",
        required=True,
        choices=[
            "huggingface",
            "openai",
            "anthropic",
            "aws_bedrock",
            "local",
            "ollama",
        ],
        help="Model provider / adapter to use",
    )
    scan_parser.add_argument(
        "--profile",
        default="standard",
        choices=["quick", "standard", "deep", "custom"],
        help="Run profile to control scanner defaults and intensity",
    )
    scan_parser.add_argument(
        "--scanners",
        "-s",
        nargs="+",
        default=None,
        help="Scanner plugins to run (default depends on profile)",
    )
    scan_parser.add_argument(
        "--connectors",
        "-c",
        nargs="+",
        default=None,
        help="SIEM/security tool connectors to push results to",
    )
    scan_parser.add_argument(
        "--output",
        "-o",
        default="markdown",
        choices=["markdown", "json", "html"],
        help="Report output format",
    )
    scan_parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Save report to file path",
    )
    scan_parser.add_argument("--device", help="Device for local models (cpu/cuda/mps)")
    scan_parser.add_argument(
        "--api-key",
        help="API key for cloud providers (WARNING: visible in process list; prefer --api-key-file or COMMUNITY_AI_AUDIT_API_KEY env var)",
    )
    scan_parser.add_argument("--api-key-file", help="Read API key from file (safer than --api-key)")
    scan_parser.add_argument(
        "--input-shape",
        default=None,
        help="Optional adversarial probe input shape as JSON list, e.g. '[32,16]'",
    )
    scan_parser.add_argument(
        "--probe-inputs",
        default=None,
        help="Optional probe inputs as JSON nested list",
    )
    scan_parser.add_argument(
        "--probe-file",
        default=None,
        help="Optional probe dataset file (.json/.jsonl/.csv) for scanners",
    )
    scan_parser.add_argument("--user", help="Username for RBAC authentication")
    scan_parser.add_argument(
        "--api-key-rbac", dest="rbac_api_key", help="API key for RBAC authentication"
    )

    # ── interpret command ───────────────────────────────────
    interp_parser = subparsers.add_parser(
        "interpret", help="Run interpretability methods on a model"
    )
    interp_parser.add_argument("model", help="Model identifier")
    interp_parser.add_argument(
        "--provider",
        "-p",
        required=True,
        choices=[
            "huggingface",
            "openai",
            "anthropic",
            "aws_bedrock",
            "local",
            "ollama",
        ],
        help="Model provider / adapter to use",
    )
    interp_parser.add_argument(
        "--interpreters",
        "-i",
        nargs="+",
        default=None,
        help="Interpreter plugins to run (default: all discovered)",
    )
    interp_parser.add_argument(
        "--input",
        dest="input_data",
        help="Input data to interpret (for text: a string; for image: path)",
    )
    interp_parser.add_argument(
        "--output",
        "-o",
        default="markdown",
        choices=["markdown", "json", "html"],
        help="Report output format",
    )
    interp_parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Save report to file path",
    )
    interp_parser.add_argument("--device", help="Device for local models")
    interp_parser.add_argument(
        "--api-key",
        help="API key for cloud providers (WARNING: visible in process list; prefer --api-key-file or COMMUNITY_AI_AUDIT_API_KEY env var)",
    )
    interp_parser.add_argument(
        "--api-key-file", help="Read API key from file (safer than --api-key)"
    )
    interp_parser.add_argument("--user", help="Username for RBAC authentication")
    interp_parser.add_argument(
        "--api-key-rbac", dest="rbac_api_key", help="API key for RBAC authentication"
    )

    # ── audit command ─────────────────────────────────────────
    audit_parser = subparsers.add_parser("audit", help="Run full audit (scan + interpret)")
    audit_parser.add_argument("model", help="Model identifier")
    audit_parser.add_argument(
        "--provider",
        "-p",
        required=True,
        choices=[
            "huggingface",
            "openai",
            "anthropic",
            "aws_bedrock",
            "local",
            "ollama",
        ],
        help="Model provider / adapter to use",
    )
    audit_parser.add_argument(
        "--profile",
        default="standard",
        choices=["quick", "standard", "deep", "custom"],
        help="Run profile to control scanner/interpreter defaults and intensity",
    )
    audit_parser.add_argument(
        "--scanners",
        "-s",
        nargs="+",
        default=None,
        help="Scanner plugins to run (default depends on profile)",
    )
    audit_parser.add_argument(
        "--interpreters",
        "-i",
        nargs="+",
        default=None,
        help="Interpreter plugins to run (default depends on profile)",
    )
    audit_parser.add_argument(
        "--input",
        dest="input_data",
        help="Input data for interpretability (required if using interpreters)",
    )
    audit_parser.add_argument(
        "--output",
        "-o",
        default="markdown",
        choices=["markdown", "json", "html"],
        help="Report output format",
    )
    audit_parser.add_argument(
        "--connectors",
        "-c",
        nargs="+",
        default=None,
        help="SIEM/security tool connectors to push results to",
    )
    audit_parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Save report to file path",
    )
    audit_parser.add_argument("--device", help="Device for local models")
    audit_parser.add_argument(
        "--api-key",
        help="API key for cloud providers (WARNING: visible in process list; prefer --api-key-file or COMMUNITY_AI_AUDIT_API_KEY env var)",
    )
    audit_parser.add_argument(
        "--api-key-file", help="Read API key from file (safer than --api-key)"
    )
    audit_parser.add_argument("--user", help="Username for RBAC authentication")
    audit_parser.add_argument(
        "--api-key-rbac", dest="rbac_api_key", help="API key for RBAC authentication"
    )
    audit_parser.add_argument(
        "--input-shape",
        default=None,
        help="Optional adversarial probe input shape as JSON list, e.g. '[32,16]'",
    )
    audit_parser.add_argument(
        "--probe-inputs",
        default=None,
        help="Optional probe inputs as JSON nested list",
    )
    audit_parser.add_argument(
        "--probe-file",
        default=None,
        help="Optional probe dataset file (.json/.jsonl/.csv) for scanners",
    )

    # ── discover command ──────────────────────────────────────
    disco_parser = subparsers.add_parser(
        "discover", help="List all discovered plugins and adapters"
    )
    disco_parser.add_argument(
        "--format", choices=["json", "table"], default="table", help="Output style"
    )

    # ── schedule command ──────────────────────────────────────
    sched_parser = subparsers.add_parser("schedule", help="Manage recurring audit schedules")
    sched_sub = sched_parser.add_subparsers(dest="schedule_command", help="Schedule actions")

    sched_add = sched_sub.add_parser("add", help="Add a new schedule")
    sched_add.add_argument("name", help="Schedule name")
    sched_add.add_argument("model", help="Model identifier")
    sched_add.add_argument("--provider", "-p", required=True, help="Model provider")
    sched_add.add_argument(
        "--cron", required=True, help="Cron expression (5-field, e.g. '0 0 * * *')"
    )
    sched_add.add_argument("--scanners", "-s", nargs="+", default=None, help="Scanners to run")
    sched_add.add_argument(
        "--interpreters", "-i", nargs="+", default=None, help="Interpreters to run"
    )
    sched_add.add_argument(
        "--connectors", "-c", nargs="+", default=None, help="Connectors to push to"
    )
    sched_add.add_argument(
        "--profile",
        default="standard",
        choices=["quick", "standard", "deep", "custom"],
        help="Run profile",
    )
    sched_add.add_argument(
        "--output",
        choices=["markdown", "json", "html"],
        default="markdown",
        help="Report output format",
    )
    sched_add.add_argument("--save-dir", default="./output", help="Directory to save reports")

    sched_sub.add_parser("list", help="List all schedules")
    sched_remove = sched_sub.add_parser("remove", help="Remove a schedule")
    sched_remove.add_argument("name", help="Schedule name to remove")

    sched_run = sched_sub.add_parser("run", help="Execute due schedules now")
    sched_run.add_argument("--name", default=None, help="Run a specific schedule by name")

    # ── eval command ──────────────────────────────────────────
    eval_parser = subparsers.add_parser(
        "eval", help="Run a full evaluation (scan + policy + reliability + scoring)"
    )
    eval_parser.add_argument("model", help="Model identifier")
    eval_parser.add_argument(
        "--provider",
        "-p",
        required=True,
        choices=["huggingface", "openai", "anthropic", "aws_bedrock", "local", "ollama"],
        help="Model provider / adapter to use",
    )
    eval_parser.add_argument(
        "--scanners",
        "-s",
        nargs="+",
        default=None,
        help="Scanner plugins to run (default: all)",
    )
    eval_parser.add_argument(
        "--policies",
        nargs="+",
        default=None,
        help="Policy checks to run (default: all)",
    )
    eval_parser.add_argument(
        "--reliability",
        nargs="+",
        default=None,
        help="Reliability scanners to run (default: none)",
    )
    eval_parser.add_argument(
        "--output",
        "-o",
        default="json",
        choices=["json", "markdown"],
        help="Output format",
    )
    eval_parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Save report to file path",
    )
    eval_parser.add_argument("--device", help="Device for local models")
    eval_parser.add_argument(
        "--api-key",
        help="API key (visible in process list; prefer env var or --api-key-file)",
    )
    eval_parser.add_argument(
        "--api-key-file",
        help="Read API key from file (safer than --api-key)",
    )
    eval_parser.add_argument(
        "--probe-file",
        default=None,
        help="Optional probe dataset file (.json/.jsonl/.csv)",
    )
    eval_parser.add_argument(
        "--scoring-weight",
        nargs=2,
        action="append",
        metavar=("DIMENSION", "VALUE"),
        default=[],
        help="Scoring weight override, e.g. --scoring-weight security 0.5",
    )

    # ── benchmark command ─────────────────────────────────────
    bench_parser = subparsers.add_parser("benchmark", help="Run model against a benchmark dataset")
    bench_parser.add_argument("model", help="Model identifier")
    bench_parser.add_argument(
        "--provider",
        "-p",
        required=True,
        choices=["huggingface", "openai", "anthropic", "aws_bedrock", "local", "ollama"],
        help="Model provider / adapter to use",
    )
    bench_parser.add_argument(
        "--dataset",
        "-d",
        required=True,
        help="Dataset name (built-in: safety, factuality) or path to custom dataset file",
    )
    bench_parser.add_argument(
        "--dataset-version",
        default="latest",
        help="Dataset version string (default: latest)",
    )
    bench_parser.add_argument(
        "--sample-limit",
        type=int,
        default=None,
        help="Limit number of test samples",
    )
    bench_parser.add_argument(
        "--output",
        "-o",
        default="json",
        choices=["json", "table"],
        help="Output format",
    )
    bench_parser.add_argument("--device", help="Device for local models")
    bench_parser.add_argument("--api-key", help="API key for cloud providers")
    bench_parser.add_argument("--api-key-file", help="Read API key from file")

    # ── regression command ────────────────────────────────────
    reg_parser = subparsers.add_parser(
        "regression", help="Compare two benchmark runs for regression"
    )
    reg_parser.add_argument("baseline_id", help="Run ID or path to baseline result JSON")
    reg_parser.add_argument("current_id", help="Run ID or path to current result JSON")
    reg_parser.add_argument(
        "--threshold",
        type=float,
        default=0.05,
        help="Minimum delta to flag as regression (default: 0.05)",
    )
    reg_parser.add_argument(
        "--output",
        "-o",
        default="json",
        choices=["json", "table"],
        help="Output format",
    )

    # ── datasets command ──────────────────────────────────────
    datasets_parser = subparsers.add_parser("datasets", help="List available benchmark datasets")
    datasets_parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output style",
    )

    # ── agent-audit command ──────────────────────────────────
    agent_audit_parser = subparsers.add_parser(
        "agent-audit", help="Run agent audit scanners on a session"
    )
    agent_audit_parser.add_argument(
        "--session-file",
        "-f",
        help="Path to agent session JSON file",
    )
    agent_audit_parser.add_argument(
        "--agent-id",
        default="unknown-agent",
        help="Agent identifier",
    )
    agent_audit_parser.add_argument(
        "--scanners",
        nargs="+",
        default=None,
        help="Agent scanners to run (default: all)",
    )
    agent_audit_parser.add_argument(
        "--output",
        "-o",
        default="json",
        choices=["json", "table"],
        help="Output format",
    )
    agent_audit_parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Save results to file path",
    )

    # ── agent-trace command ──────────────────────────────────
    agent_trace_parser = subparsers.add_parser(
        "agent-trace", help="Manage and export agent execution traces"
    )
    agent_trace_sub = agent_trace_parser.add_subparsers(dest="trace_command", help="Trace actions")
    trace_replay = agent_trace_sub.add_parser("replay", help="Replay a trace from a session file")
    trace_replay.add_argument("session_file", help="Path to session JSON file")
    trace_replay.add_argument("--step", type=int, default=None, help="Replay a single step number")
    trace_export = agent_trace_sub.add_parser("export", help="Export a trace to a file")
    trace_export.add_argument("session_file", help="Path to session JSON file")
    trace_export.add_argument(
        "--format",
        choices=["json", "jsonl", "html", "markdown"],
        default="json",
        help="Export format",
    )
    trace_export.add_argument(
        "--output", "-o", default=None, help="Output file path (default: based on session ID)"
    )

    # ── agent-dashboard command ──────────────────────────────
    dash_parser = subparsers.add_parser(
        "agent-dashboard", help="Generate agent monitoring dashboard"
    )
    dash_parser.add_argument(
        "--output", "-o", default="dashboard.html", help="Output HTML file path"
    )
    dash_parser.add_argument(
        "--format", choices=["html", "json"], default="html", help="Dashboard output format"
    )
    dash_parser.add_argument(
        "--history-limit", type=int, default=100, help="Number of audit records to include"
    )

    # ── agent-monitor command ────────────────────────────────
    agent_monitor_parser = subparsers.add_parser(
        "agent-monitor", help="Manage agent monitoring and alerts"
    )
    agent_monitor_sub = agent_monitor_parser.add_subparsers(
        dest="monitor_command", help="Monitor actions"
    )
    mon_audit = agent_monitor_sub.add_parser("audit", help="Run a manual agent audit")
    mon_audit.add_argument("agent_id", help="Agent identifier")
    mon_audit.add_argument(
        "--session-file", "-f", required=True, help="Path to agent session JSON file"
    )
    mon_audit.add_argument("--scanners", nargs="+", default=None, help="Scanners to run")
    mon_history = agent_monitor_sub.add_parser("history", help="Show audit history")
    mon_history.add_argument("--agent-id", default=None, help="Filter by agent ID")
    mon_history.add_argument("--limit", type=int, default=20, help="Number of records")
    mon_history.add_argument("--format", choices=["json", "table"], default="table")
    mon_alerts = agent_monitor_sub.add_parser("alerts", help="Show recent alerts")
    mon_alerts.add_argument("--limit", type=int, default=20)
    mon_alerts.add_argument("--level", default=None, choices=["info", "warning", "critical"])
    mon_alerts.add_argument("--clear", action="store_true", help="Clear all alerts")
    mon_drift = agent_monitor_sub.add_parser("drift", help="Check for drift")
    mon_drift.add_argument("--threshold", type=float, default=10.0, help="Drift threshold")
    mon_drift.add_argument("--baseline", type=int, default=20, help="Baseline window size")

    # ── redteam command ────────────────────────────────────────
    redteam_parser = subparsers.add_parser(
        "redteam", help="Run red team security testing against a model"
    )
    redteam_parser.add_argument("model", help="Model identifier")
    redteam_parser.add_argument(
        "--provider",
        "-p",
        required=True,
        choices=["huggingface", "openai", "anthropic", "aws_bedrock", "local", "ollama"],
        help="Model provider",
    )
    redteam_parser.add_argument(
        "--scanners",
        nargs="+",
        default=None,
        help="Red team scanners to run (default: all)",
    )
    redteam_parser.add_argument("--device", help="Device for local models")
    redteam_parser.add_argument("--api-key", help="API key for cloud providers")
    redteam_parser.add_argument("--api-key-file", help="Read API key from file")
    redteam_parser.add_argument(
        "--output",
        "-o",
        default="json",
        choices=["json", "table"],
        help="Output format",
    )

    # ── mechinterp command ────────────────────────────────────
    mechinterp_parser = subparsers.add_parser(
        "mechinterp", help="Run mechanistic interpretability analysis"
    )
    mechinterp_parser.add_argument("model", help="Model identifier")
    mechinterp_parser.add_argument(
        "--provider",
        "-p",
        required=True,
        choices=["huggingface", "openai", "anthropic", "aws_bedrock", "local", "ollama"],
        help="Model provider",
    )
    mechinterp_parser.add_argument(
        "--analyzers",
        nargs="+",
        default=None,
        help="Analyzers to run (default: all)",
    )
    mechinterp_parser.add_argument("--device", help="Device for local models")
    mechinterp_parser.add_argument("--api-key", help="API key for cloud providers")
    mechinterp_parser.add_argument("--api-key-file", help="Read API key from file")
    mechinterp_parser.add_argument(
        "--output",
        "-o",
        default="json",
        choices=["json", "table"],
        help="Output format",
    )

    # ── alignment command ─────────────────────────────────────
    alignment_parser = subparsers.add_parser(
        "alignment", help="Run alignment evaluation on a model"
    )
    alignment_parser.add_argument("model", help="Model identifier")
    alignment_parser.add_argument(
        "--provider",
        "-p",
        required=True,
        choices=["huggingface", "openai", "anthropic", "aws_bedrock", "local", "ollama"],
        help="Model provider",
    )
    alignment_parser.add_argument(
        "--scanners",
        nargs="+",
        default=None,
        help="Alignment scanners to run (default: all)",
    )
    alignment_parser.add_argument("--device", help="Device for local models")
    alignment_parser.add_argument("--api-key", help="API key for cloud providers")
    alignment_parser.add_argument("--api-key-file", help="Read API key from file")
    alignment_parser.add_argument(
        "--output",
        "-o",
        default="json",
        choices=["json", "table"],
        help="Output format",
    )

    # ── audit-score command ────────────────────────────────────
    audit_score_parser = subparsers.add_parser(
        "audit-score", help="Compute unified audit score from all results"
    )
    audit_score_parser.add_argument(
        "--scan", type=str, default=None, help="Path to scan results JSON"
    )
    audit_score_parser.add_argument(
        "--policy", type=str, default=None, help="Path to policy results JSON"
    )
    audit_score_parser.add_argument(
        "--reliability", type=str, default=None, help="Path to reliability results JSON"
    )
    audit_score_parser.add_argument(
        "--agent", type=str, default=None, help="Path to agent audit results JSON"
    )
    audit_score_parser.add_argument(
        "--redteam", type=str, default=None, help="Path to red team results JSON"
    )
    audit_score_parser.add_argument(
        "--alignment", type=str, default=None, help="Path to alignment results JSON"
    )
    audit_score_parser.add_argument(
        "--mechinterp", type=str, default=None, help="Path to mechinterp results JSON"
    )
    audit_score_parser.add_argument(
        "--weights",
        nargs=2,
        action="append",
        metavar=("DIMENSION", "VALUE"),
        default=[],
        help="Weight override, e.g. --weights security 0.3",
    )
    audit_score_parser.add_argument(
        "--output",
        "-o",
        default="json",
        choices=["json", "table"],
        help="Output format",
    )

    # ── RBAC global flags ─────────────────────────────────────
    for sub in (sched_parser, eval_parser, bench_parser):
        sub.add_argument("--user", help="Username for RBAC authentication")
        sub.add_argument(
            "--api-key-rbac",
            dest="rbac_api_key",
            help="API key for RBAC authentication",
        )

    return parser


# ─────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Set up logging
    _setup_logging(args.verbose)

    if args.command is None:
        ui.print_banner()
        parser.print_help()
        return 1

    ui.install_traceback_handler()
    ui.print_banner()

    # Lazy import to avoid slow startup for --help
    from community_ai_audit.core.audit import AuditEngine

    extra_paths = os.environ.get("COMMUNITY_AI_AUDIT_PLUGIN_PATH", "").split(":")
    extra_paths = [p for p in extra_paths if p]

    engine = AuditEngine(
        config_path=args.config,
        extra_plugin_paths=extra_paths,
    )

    if args.command == "discover":
        return _cmd_discover(engine, args)

    if args.command == "scan":
        return _cmd_scan(engine, args)

    if args.command == "interpret":
        return _cmd_interpret(engine, args)

    if args.command == "audit":
        return _cmd_audit(engine, args)

    if args.command == "schedule":
        return _cmd_schedule(engine, args)

    if args.command == "eval":
        return _cmd_eval(engine, args)

    if args.command == "benchmark":
        return _cmd_benchmark(engine, args)

    if args.command == "regression":
        return _cmd_regression(args)

    if args.command == "datasets":
        return _cmd_datasets(args)

    if args.command == "agent-audit":
        return _cmd_agent_audit(args)

    if args.command == "agent-trace":
        return _cmd_agent_trace(args)

    if args.command == "agent-dashboard":
        return _cmd_agent_dashboard(args)

    if args.command == "agent-monitor":
        return _cmd_agent_monitor(args)

    if args.command == "redteam":
        return _cmd_redteam(args)

    if args.command == "mechinterp":
        return _cmd_mechinterp(args)

    if args.command == "alignment":
        return _cmd_alignment(args)

    if args.command == "audit-score":
        return _cmd_audit_score(args)

    return 0


def _rbac_check(args) -> None:
    """Authenticate and authorize the current user if RBAC is configured."""
    user = getattr(args, "user", None)
    api_key = getattr(args, "api_key", None) or getattr(args, "rbac_api_key", None)
    if not user:
        return  # RBAC not enforced unless --user is provided
    from community_ai_audit.core.rbac import AccessControl, RBACConfig

    rbac_config = RBACConfig()
    ac = AccessControl(rbac_config)
    if api_key and not ac.authenticate(user, api_key):
        raise RBACPermError(user, "authenticate")
    if not ac.authenticate(user, None):
        raise RBACPermError(user, "authenticate")


def _cmd_schedule(engine, args) -> int:
    """Manage and run recurring audit schedules."""
    try:
        _rbac_check(args)
    except (PermissionError, RBACPermError) as e:
        ui.error(f"Access denied: {e}")
        return 1
    from community_ai_audit.core.scheduler import AuditScheduler

    scheduler = AuditScheduler()
    cmd = args.schedule_command

    if cmd == "add":
        try:
            scheduler.add_schedule(
                name=args.name,
                cron=args.cron,
                model_id=args.model,
                provider=args.provider,
                scanners=args.scanners,
                interpreters=args.interpreters,
                connectors=args.connectors,
                profile=args.profile,
                output_format=args.output,
            )
            ui.success(f"Schedule '{args.name}' added (cron: {args.cron})")
        except Exception as e:
            ui.error(f"Failed to add schedule: {e}")
            return 1

    elif cmd == "list":
        schedules = scheduler.list_schedules()
        if not schedules:
            ui.info("No schedules configured.")
        else:
            for s in schedules:
                next_run = scheduler._get_next_run(s.get("cron", ""))
                ui.info(
                    f"  {s['name']} | cron: {s.get('cron', '')} | "
                    f"model: {s.get('model_id', '')} | "
                    f"next: {next_run or 'N/A'}"
                )
                ui.info(f"  {'':20s} | scanners: {', '.join(s.get('scanners', [])) or '(all)'}")

    elif cmd == "remove":
        try:
            scheduler.remove_schedule(args.name)
            ui.success(f"Schedule '{args.name}' removed.")
        except KeyError:
            ui.error(f"Schedule '{args.name}' not found.")
            return 1

    elif cmd == "run":
        if args.name:
            all_schedules = scheduler.list_schedules()
            found = [s for s in all_schedules if s["name"] == args.name]
            if not found:
                ui.error(f"Schedule '{args.name}' not found.")
                return 1
            schedules_to_run = [(found[0], scheduler._get_next_run(found[0].get("cron", "")))]
        else:
            schedules_to_run = scheduler.get_due_schedules()

        if not schedules_to_run:
            ui.info("No schedules due.")
            return 0

        for sched, _ in schedules_to_run:
            ui.info(f"Running schedule '{sched['name']}'...")
            try:
                results = scheduler.run_due(engine)
                if results:
                    for r in results:
                        ui.info(f"  {r.get('name', '?')} -> {r.get('status', '?')}")
                ui.success(f"Schedule '{sched['name']}' completed.")
            except Exception as e:
                ui.error(f"Schedule '{sched['name']}' failed: {e}")
                return 1

    else:
        ui.error("Unknown schedule command. Use: add, list, remove, run")
        return 1

    return 0


def _cmd_discover(engine, args) -> int:
    """List all discovered plugins, adapters, and connectors."""

    caps = engine.list_capabilities()

    if args.format == "json":
        ui.print_json(caps)
    else:
        ui.print_discover(caps, format="tree")

    return 0


def _cmd_scan(engine, args) -> int:
    """Run scanners."""
    import json as _json
    from community_ai_audit.reporting import ReportGenerator

    try:
        _rbac_check(args)
    except (PermissionError, RBACPermError) as e:
        ui.error(f"Access denied: {e}")
        return 1

    adapter_config = _build_adapter_config(args, engine.config)
    model_id = args.model

    ui.header("Security Scan", f"{model_id} ({args.provider})")
    with ui.progress_context("Loading model...") as progress:
        progress.add_task("Loading model...", total=None)
        engine.load_model(model_id, provider=args.provider, adapter_config=adapter_config)

    selected_scanners, _selected_interpreters, profile_overrides = _apply_profile_defaults(
        profile=getattr(args, "profile", "standard"),
        scanners=args.scanners,
        interpreters=None,
    )
    scanner_overrides = _merge_overrides(profile_overrides, _build_scanner_overrides(args))

    ui.info(f"Running {len(selected_scanners)} scanners...")
    scanner_names = selected_scanners or []

    for name in ui.task_progress(scanner_names, "Scanning"):
        pass

    results = engine.scan(scanners=selected_scanners, config_overrides=scanner_overrides)

    reporter = ReportGenerator()
    if args.output == "json":
        report = _json.dumps([r.to_dict() for r in results], indent=2)
        ui.print_json(report)
    else:
        for r in results:
            findings = getattr(r, "findings", [])
            finding_dicts = []
            for f in findings:
                finding_dicts.append({
                    "severity": getattr(f, "severity", "unknown"),
                    "description": getattr(f, "description", str(f)),
                    "category": getattr(f, "category", "general"),
                })
            if finding_dicts:
                ui.print_findings(finding_dicts, title=f"{r.scanner_name} Findings")
            else:
                ui.success(f"{r.scanner_name}: no findings")

    if args.save:
        _save_report(report if args.output == "json" else reporter.render_scan_results(results, fmt=args.output), args.save)

    if args.connectors:
        connector_configs = _build_connector_configs(args, engine.config)
        connector_results = engine._push_to_connectors(results, [], args.connectors, connector_configs)
        for name, status in connector_results.items():
            ui.info(f"Connector {name}: {status}")

    highest = max(
        (r.overall_severity for r in results),
        key=lambda s: _severity_rank(s),
        default=None,
    )
    if highest is None:
        return 0
    sev_str = getattr(highest, "value", str(highest)).lower()
    if sev_str == "critical":
        return 2
    if sev_str in ("high", "medium"):
        return 1
    return 0


def _cmd_interpret(engine, args) -> int:
    """Run interpreters."""
    import json as _json
    from community_ai_audit.reporting import ReportGenerator

    try:
        _rbac_check(args)
    except (PermissionError, RBACPermError) as e:
        ui.error(f"Access denied: {e}")
        return 1

    adapter_config = _build_adapter_config(args, engine.config)
    model_id = args.model

    ui.header("Model Interpretation", f"{model_id} ({args.provider})")
    with ui.progress_context("Loading model...") as progress:
        progress.add_task("Loading model...", total=None)
        engine.load_model(model_id, provider=args.provider, adapter_config=adapter_config)

    raw_input = args.input_data or "Explain this model's decision for a neutral statement."
    inputs = _parse_input_value(raw_input)

    ui.info("Running interpreters...")
    results = engine.interpret(inputs=inputs, interpreters=args.interpreters)

    reporter = ReportGenerator()
    if args.output == "json":
        report = _json.dumps([r.to_dict() for r in results], indent=2)
        ui.print_json(report)
    else:
        for r in results:
            ui.panel(
                getattr(r, "interpreter_name", "Interpretation"),
                str(getattr(r, "summary", str(r))),
                style="magenta",
            )

    if args.save:
        _save_report(report if args.output == "json" else reporter.render_interpret_results(results, fmt=args.output), args.save)

    return 0


def _cmd_audit(engine, args) -> int:
    """Run full audit."""
    import json as _json
    from community_ai_audit.reporting import ReportGenerator

    try:
        _rbac_check(args)
    except (PermissionError, RBACPermError) as e:
        ui.error(f"Access denied: {e}")
        return 1

    adapter_config = _build_adapter_config(args, engine.config)
    model_id = args.model

    ui.header("Full Security Audit", f"{model_id} ({args.provider})")
    with ui.progress_context("Loading model...") as progress:
        progress.add_task("Loading model...", total=None)
        engine.load_model(model_id, provider=args.provider, adapter_config=adapter_config)

    selected_scanners, selected_interpreters, profile_overrides = _apply_profile_defaults(
        profile=getattr(args, "profile", "standard"),
        scanners=args.scanners,
        interpreters=args.interpreters,
    )

    parsed_inputs = _parse_input_value(args.input_data) if args.input_data else None
    scanner_overrides = _merge_overrides(profile_overrides, _build_scanner_overrides(args))
    run_metadata = _build_run_metadata(args, scanner_overrides)
    connector_configs = _build_connector_configs(args, engine.config)

    ui.info(f"Running {len(selected_scanners)} scanners and {len(selected_interpreters)} interpreters...")
    session = engine.audit(
        scanners=selected_scanners,
        interpreters=selected_interpreters,
        inputs=parsed_inputs if selected_interpreters else None,
        connectors=args.connectors,
        connector_configs=connector_configs,
        config_overrides=scanner_overrides,
        run_metadata=run_metadata,
    )

    reporter = ReportGenerator()
    if args.output == "json":
        report = _json.dumps(session.to_dict(), indent=2, default=str)
        ui.print_json(report)
    else:
        report = reporter.render_session(session, fmt=args.output)
        ui.success(f"Audit complete: {session.summary()}")

    if args.save:
        _save_report(report, args.save)

    highest = (
        session.highest_severity.name
        if hasattr(session.highest_severity, "name")
        else str(session.highest_severity)
    )
    if highest == "CRITICAL":
        return 2
    if highest in ("HIGH", "MEDIUM"):
        return 1
    return 0


def _read_api_key(args) -> Optional[str]:
    """Read API key from env var, --api-key-file, or --api-key (in order of preference).

    --api-key-file and --api-key both warn about security.
    """
    env_key = os.environ.get("COMMUNITY_AI_AUDIT_API_KEY")
    if env_key:
        return env_key

    api_key_file = getattr(args, "api_key_file", None)
    if api_key_file:
        try:
            with open(api_key_file) as f:
                return f.read().strip()
        except OSError as exc:
            print(f"Warning: could not read --api-key-file '{api_key_file}': {exc}")

    api_key = getattr(args, "api_key", None)
    if api_key:
        print(
            "Warning: --api-key is visible in process listings. "
            "Use COMMUNITY_AI_AUDIT_API_KEY env var or --api-key-file instead."
        )
        return api_key

    return None


def _build_adapter_config(args, engine_config: dict | None = None) -> dict:
    """Build adapter config from CLI args + environment + config file."""
    config = {}
    if hasattr(args, "device") and args.device:
        config["device"] = args.device

    api_key = _read_api_key(args)
    if api_key:
        config["api_key"] = api_key

    # Also pull adapter-specific config from config file
    if engine_config and "adapters" in engine_config:
        provider = getattr(args, "provider", None)
        if provider and provider in engine_config["adapters"]:
            config.update(engine_config["adapters"][provider])

    return config


def _save_report(report: str, path: str) -> None:
    with open(path, "w") as f:
        f.write(report)
    print(f"Report saved to: {path}")


def _parse_input_value(value: Any) -> Any:
    """Parse CLI input value as JSON when possible; otherwise return raw string."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    text = value.strip()
    if (text.startswith("[") and text.endswith("]")) or (
        text.startswith("{") and text.endswith("}")
    ):
        try:
            return json.loads(text)
        except Exception:
            return value
    return value


def _build_scanner_overrides(args) -> dict:
    overrides = {}
    common = {}

    if hasattr(args, "input_shape") and args.input_shape:
        parsed = _parse_input_value(args.input_shape)
        if isinstance(parsed, list):
            common["input_shape"] = parsed

    if hasattr(args, "probe_inputs") and args.probe_inputs:
        parsed = _parse_input_value(args.probe_inputs)
        if isinstance(parsed, list):
            common["probe_inputs"] = parsed

    if hasattr(args, "probe_file") and args.probe_file:
        loaded = _load_probe_file(args.probe_file)
        if loaded:
            common["probe_inputs"] = loaded

    if common:
        overrides["adversarial"] = dict(common)
        overrides["backdoor"] = dict(common)

    return overrides


def _build_connector_configs(args, engine_config: dict | None) -> dict:
    """Build connector configs from CLI args + environment + config file."""
    configs = {}

    # Pull connector-specific config from config file
    if engine_config and "connectors" in engine_config:
        for name, config in engine_config["connectors"].items():
            configs[name] = config

    return configs


def _load_probe_file(path: str) -> List[List[float]]:
    """Load probe inputs from .json/.jsonl/.csv.

    Returns a nested list suitable for scanner `probe_inputs`.
    """
    import csv
    from pathlib import Path

    p = Path(path).expanduser()
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Probe file not found: {p}")

    allowed_suffixes = {".json", ".jsonl", ".ndjson", ".csv"}
    if p.suffix.lower() not in allowed_suffixes:
        raise ValueError(
            f"Unsupported probe file extension '{p.suffix}'; "
            f"allowed: {', '.join(sorted(allowed_suffixes))}"
        )

    suffix = p.suffix.lower()

    if suffix == ".json":
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return _normalize_probe_rows(data)

    if suffix in {".jsonl", ".ndjson"}:
        rows = []
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                rows.append(obj)
        return _normalize_probe_rows(rows)

    if suffix == ".csv":
        rows = []
        with p.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                parsed_row = []
                ok = True
                for cell in row:
                    try:
                        parsed_row.append(float(cell))
                    except ValueError:
                        ok = False
                        break
                if ok:
                    rows.append(parsed_row)
        return rows

    raise ValueError(f"Unsupported probe file type: {suffix}")


def _normalize_probe_rows(data: Any) -> List[List[float]]:
    """Normalize flexible JSON probe format to List[List[float]]."""
    if isinstance(data, list):
        if not data:
            return []
        if isinstance(data[0], (int, float)):
            return [list(map(float, data))]
        out = []
        for item in data:
            if isinstance(item, dict):
                if "input" in item and isinstance(item["input"], list):
                    out.append([float(v) for v in item["input"]])
                elif "features" in item and isinstance(item["features"], list):
                    out.append([float(v) for v in item["features"]])
            elif isinstance(item, list):
                out.append([float(v) for v in item])
        return out
    return []


def _apply_profile_defaults(profile: str, scanners=None, interpreters=None):
    """Apply profile-based defaults for scanners/interpreters and intensity."""
    profile = (profile or "standard").lower()

    default_scanners = {
        "quick": ["adversarial"],
        "standard": ["adversarial", "backdoor"],
        "deep": ["adversarial", "backdoor"],
        "custom": scanners or [],
    }
    default_interpreters = {
        "quick": ["integrated-gradients"],
        "standard": ["integrated-gradients"],
        "deep": ["integrated-gradients", "lime"],
        "custom": interpreters or [],
    }

    selected_scanners = (
        scanners if scanners else default_scanners.get(profile, default_scanners["standard"])
    )
    selected_interpreters = (
        interpreters
        if interpreters
        else default_interpreters.get(profile, default_interpreters["standard"])
    )

    profile_overrides = {}
    if profile == "quick":
        profile_overrides = {
            "adversarial": {"num_samples": 16, "pgd_steps": 5},
            "backdoor": {"sample_size": 64, "max_layers": 8},
        }
    elif profile == "standard":
        profile_overrides = {
            "adversarial": {"num_samples": 32, "pgd_steps": 10},
            "backdoor": {"sample_size": 128, "max_layers": 16},
        }
    elif profile == "deep":
        profile_overrides = {
            "adversarial": {"num_samples": 128, "pgd_steps": 20},
            "backdoor": {"sample_size": 512, "max_layers": 32},
            "integrated-gradients": {"steps": 100},
            "lime": {"num_samples": 2000},
        }

    return selected_scanners, selected_interpreters, profile_overrides


def _merge_overrides(base: dict, extra: dict) -> dict:
    merged = dict(base or {})
    for key, value in (extra or {}).items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def _build_run_metadata(args, scanner_overrides: dict) -> dict:
    profile = getattr(args, "profile", "standard")
    meta = {
        "profile": profile,
        "provider": getattr(args, "provider", None),
        "probe_source": None,
        "probe_count": None,
    }

    if hasattr(args, "probe_file") and args.probe_file:
        meta["probe_source"] = args.probe_file
    elif hasattr(args, "probe_inputs") and args.probe_inputs:
        meta["probe_source"] = "inline:probe_inputs"
    elif hasattr(args, "input_shape") and args.input_shape:
        meta["probe_source"] = f"synthetic:input_shape={args.input_shape}"

    # try to estimate probe count from overrides
    for key in ("adversarial", "backdoor"):
        cfg = (scanner_overrides or {}).get(key, {})
        probes = cfg.get("probe_inputs")
        if isinstance(probes, list):
            meta["probe_count"] = len(probes)
            break

    return {k: v for k, v in meta.items() if v is not None}


def _severity_rank(sev) -> int:
    value = getattr(sev, "value", str(sev)).lower()
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0, "unknown": -1}
    return order.get(value, -1)


def _cmd_eval(engine: Any, args: Any) -> int:
    """Run a full evaluation."""
    try:
        _rbac_check(args)
    except (PermissionError, RBACPermError) as e:
        ui.error(f"Access denied: {e}")
        return 1

    from community_ai_audit.core.evaluation import EvaluationEngine

    scoring_weights = None
    if hasattr(args, "scoring_weight") and args.scoring_weight:
        try:
            scoring_weights = {dim: float(val) for dim, val in args.scoring_weight}
        except ValueError as e:
            ui.error(f"Invalid scoring weight: {e}")
            return 1

    eval_engine = EvaluationEngine(audit_engine=engine)

    adapter_config = _build_adapter_config(args, engine.config)
    probe_inputs = None
    if hasattr(args, "probe_file") and args.probe_file:
        probe_inputs = _load_probe_file(args.probe_file)

    ui.info(f"Evaluating model: {args.model} (provider: {args.provider}) ...")
    result = eval_engine.evaluate(
        model_id=args.model,
        provider=args.provider,
        adapter_config=adapter_config,
        scanners=args.scanners,
        policies=args.policies,
        reliability_checks=args.reliability,
        scoring_weights=scoring_weights,
        probe_inputs=probe_inputs,
    )

    if args.output == "json":
        ui.print_json(result.to_dict())
    else:
        ui.header(f"Evaluation: {result.model_id}")
        ui.info(f"Session: {result.session_id}")
        ui.info(f"Duration: {result.duration_seconds:.1f}s")
        ui.info(f"Findings: {result.total_findings}")
        ui.info(f"Policies: {result.passed_policies} passed / {result.failed_policies} failed")

        d = result.to_dict()
        if result.risk_scores:
            dims = [
                ("Security", d.get("risk_scores", {}).get("security_score", 0)),
                ("Reliability", d.get("risk_scores", {}).get("reliability_score", 0)),
                ("Compliance", d.get("risk_scores", {}).get("compliance_score", 0)),
            ]
            overall = d.get("risk_scores", {}).get("overall_score", 0)
            ui.print_overall_score(overall, *dims)

    if args.save:
        _save_report(json.dumps(result.to_dict(), indent=2), args.save)

    return 0


def _cmd_benchmark(engine: Any, args: Any) -> int:
    """Run a benchmark against a dataset."""
    try:
        _rbac_check(args)
    except (PermissionError, RBACPermError) as e:
        ui.error(f"Access denied: {e}")
        return 1

    from community_ai_audit.core.evaluation import EvaluationEngine

    eval_engine = EvaluationEngine(audit_engine=engine)

    dataset_name = args.dataset
    if os.path.exists(dataset_name) or dataset_name.endswith((".json", ".jsonl", ".yaml", ".yml")):
        from community_ai_audit.datasets.registry import load_custom_dataset

        try:
            load_custom_dataset(dataset_name)
            dataset_name = os.path.splitext(os.path.basename(dataset_name))[0]
        except Exception as e:
            ui.error(f"Failed to load custom dataset: {e}")
            return 1

    adapter_config = _build_adapter_config(args, engine.config)

    ui.header("Model Benchmark", f"{args.model} ({args.provider})")
    ui.info(f"Dataset: {dataset_name} (version: {args.dataset_version})")

    try:
        result = eval_engine.benchmark(
            model_id=args.model,
            provider=args.provider,
            dataset_name=dataset_name,
            dataset_version=args.dataset_version,
            adapter_config=adapter_config,
            sample_limit=args.sample_limit,
        )
    except ValueError as e:
        ui.error(f"Benchmark failed: {e}")
        return 1

    from community_ai_audit.datasets.models import BenchmarkRun
    from community_ai_audit.datasets.registry import record_benchmark_run

    record_benchmark_run(
        BenchmarkRun(
            run_id=f"bench-{int(time.time())}",
            dataset_name=result.dataset_name,
            dataset_version=result.dataset_version,
            model_id=result.model_id,
            adapter_name=result.adapter_name,
            accuracy=result.accuracy,
            scores=result.scores,
            num_samples=result.num_samples,
            num_passed=result.num_passed,
            num_failed=result.num_failed,
            duration_seconds=result.duration_seconds,
            metrics=result.metrics,
        )
    )

    if args.output == "json":
        ui.print_json(result.to_dict())
    else:
        ui.panel(
            f"Benchmark: {result.benchmark_name}",
            f"Dataset: {result.dataset_name} v{result.dataset_version}\n"
            f"Model: {result.model_id}\n"
            f"Samples: {result.num_samples}\n"
            f"Passed: {result.num_passed} / Failed: {result.num_failed}\n"
            f"Accuracy: [{'green' if result.accuracy > 0.8 else 'yellow'}]{result.accuracy:.3f}[/]\n"
            f"Duration: {result.duration_seconds:.1f}s",
            style="cyan",
        )

    return 0


def _cmd_regression(args: Any) -> int:
    """Compare two benchmark results for regression."""
    from community_ai_audit.core.evaluation import EvaluationEngine

    eval_engine = EvaluationEngine()

    def _load_result(path_or_id: str) -> Any:
        """Load a BenchmarkResult from file or history."""
        from community_ai_audit.datasets.registry import get_benchmark_history
        from community_ai_audit.core.evaluation.models import BenchmarkResult

        if os.path.exists(path_or_id):
            with open(path_or_id) as f:
                data = json.load(f)
            return BenchmarkResult(**{k: v for k, v in data.items() if k != "per_sample_results"})
        runs = get_benchmark_history(limit=50)
        for r in runs:
            if r.run_id == path_or_id:
                return r
        raise ValueError(f"Could not find benchmark run: {path_or_id}")

    try:
        baseline = _load_result(args.baseline_id)
        current = _load_result(args.current_id)
    except (ValueError, OSError) as e:
        ui.error(f"Failed to load benchmark results: {e}")
        return 1

    report = eval_engine.regression(
        baseline=baseline,
        current=current,
        threshold=args.threshold,
    )

    if args.output == "json":
        ui.print_json(report.to_dict())
    else:
        ui.header("Regression Report")
        ui.info(f"Baseline: {report.baseline.benchmark_name} ({report.baseline.started_at.isoformat()[:10]})")
        ui.info(f"Current:  {report.current.benchmark_name} ({report.current.started_at.isoformat()[:10]})")
        delta = report.accuracy_delta
        delta_color = "green" if delta >= 0 else "red"
        ui.info(f"Accuracy: {report.baseline.accuracy:.3f} -> {report.current.accuracy:.3f} ([{delta_color}]{delta:+.3f}[/])")
        if report.regressions:
            ui.divider()
            for r in report.regressions:
                ui.error(str(r))
        if report.improvements:
            for r in report.improvements:
                ui.success(str(r))
        if not report.has_regression and not report.has_improvement:
            ui.info(f"No significant changes detected (threshold: {report.threshold})")

    return 0


def _cmd_datasets(args: Any) -> int:
    """List available benchmark datasets."""
    from community_ai_audit.datasets.registry import list_datasets

    datasets = list_datasets()
    if not datasets:
        ui.info("No datasets available.")
        return 0

    if args.format == "json":
        ui.print_json([d.to_dict() for d in datasets])
    else:
        ui.header("Available Benchmark Datasets")
        tbl = ui.Table(box=ui.box.SIMPLE, header_style="bold cyan")
        tbl.add_column("Name", style="bold")
        tbl.add_column("Version")
        tbl.add_column("Samples", justify="right")
        tbl.add_column("Categories")
        tbl.add_column("Description")
        for ds in datasets:
            tbl.add_row(ds.name, str(ds.version), str(ds.num_samples), ", ".join(ds.categories), ds.description)
        ui._console().print(tbl)

    return 0


def _cmd_agent_audit(args: Any) -> int:
    """Run agent audit scanners on a session."""
    from community_ai_audit.core.agent_session import AgentAuditSession
    from community_ai_audit.plugins.agents import run_agent_scanners

    if args.session_file:
        with open(args.session_file) as f:
            data = json.load(f)
        session = AgentAuditSession.from_dict(data)
    else:
        ui.warning("No session file provided. Running on empty session.")
        return 1

    ui.header(f"Agent Audit: {session.agent_id}")
    ui.info(f"Session: {session.session_id[:8]}")
    tool_count = len([s for s in session.steps if hasattr(s, 'step_type') and hasattr(s.step_type, 'value') and s.step_type.value == 'tool_call'])
    ui.info(f"Tools used: {tool_count}")

    results = run_agent_scanners(scanners=args.scanners, session=session)

    if args.output == "json":
        ui.print_json(results)
    else:
        ui.print_results_table(results, title="Agent Audit Results", score_keys=["score"], extra_keys=[])

        for result in results:
            findings = result.get("findings", [])
            if findings:
                ui.print_findings(findings, title=result.get("scanner_name", "?"))

    if args.save:
        with open(args.save, "w") as f:
            f.write(json.dumps(results, indent=2, default=str))
        ui.success(f"Results saved to: {args.save}")

    return 0


def _cmd_agent_trace(args: Any) -> int:
    """Manage and export agent execution traces."""
    from community_ai_audit.core.agent_session import AgentAuditSession
    from community_ai_audit.core.tracing import Replayer, TraceExporter, ExecutionTrace

    cmd = args.trace_command

    if cmd == "replay":
        with open(args.session_file) as f:
            data = json.load(f)
        session = AgentAuditSession.from_dict(data)
        trace = ExecutionTrace(
            agent_id=session.agent_id,
            session_id=session.session_id,
            steps=session.steps,
            start_time=session.start_time,
            end_time=session.end_time,
        )
        replayer = Replayer(trace)

        if args.step:
            step = replayer.seek(args.step)
            if step:
                ui.print_json(step.to_dict())
            else:
                ui.error(f"Step {args.step} not found.")
                return 1
        else:
            ui.header(f"Trace Replay: {trace.session_id}")
            ui.info(f"Steps: {trace.step_count}")
            ui.info(f"Summary: {json.dumps(replayer.summary(), indent=2)}")
            ui.info(f"Stats: {json.dumps(replayer.stats(), indent=2)}")

    elif cmd == "export":
        with open(args.session_file) as f:
            data = json.load(f)
        session = AgentAuditSession.from_dict(data)
        trace = ExecutionTrace(
            agent_id=session.agent_id,
            session_id=session.session_id,
            steps=session.steps,
            start_time=session.start_time,
            end_time=session.end_time,
        )
        exporter = TraceExporter(trace)
        output_path = args.output or f"trace_{session.session_id[:8]}.{args.format}"
        exporter.save(output_path, fmt=args.format)
        ui.success(f"Trace exported to: {output_path}")

    else:
        ui.error("Unknown trace command. Use: replay, export")
        return 1

    return 0


def _cmd_agent_dashboard(args: Any) -> int:
    """Generate agent monitoring dashboard."""
    from community_ai_audit.dashboard_v2 import DashboardServer, DashboardConfig

    config = DashboardConfig(history_limit=args.history_limit)
    server = DashboardServer(config=config)

    if args.format == "json":
        path = server.save_json(args.output)
    else:
        path = server.save_html(args.output)

    ui.success(f"Dashboard saved to: {path}")
    return 0


def _cmd_agent_monitor(args: Any) -> int:
    """Manage agent monitoring and alerts."""
    from community_ai_audit.monitoring import (
        AgentAuditor,
        AlertManager,
        DriftDetector,
    )

    cmd = args.monitor_command

    if cmd == "audit":
        from community_ai_audit.core.agent_session import AgentAuditSession

        with open(args.session_file) as f:
            data = json.load(f)
        session = AgentAuditSession.from_dict(data)

        auditor = AgentAuditor()
        result = auditor.audit_session(
            session=session,
            scanners=args.scanners,
        )
        ui.print_json(result)

    elif cmd == "history":
        auditor = AgentAuditor()
        history = auditor.get_history(limit=args.limit, agent_id=args.agent_id)

        if args.format == "json":
            ui.print_json(history)
        else:
            ui.header(f"Audit History (last {len(history)} records)")
            for record in history:
                ts = record.get("timestamp", "")[:19]
                agent = record.get("agent_id", "?")
                score = record.get("overall_score", "?")
                scanner_count = len(record.get("scanner_results", []))
                ui.info(f"{ts} | {agent} | score: {score} | scanners: {scanner_count}")

    elif cmd == "alerts":
        alert_manager = AlertManager()
        if args.clear:
            count = alert_manager.clear_alerts()
            ui.success(f"Cleared {count} alerts.")
            return 0

        from community_ai_audit.monitoring.alerts import AlertLevel

        level = AlertLevel(args.level) if args.level else None
        alerts = alert_manager.get_alerts(limit=args.limit, level=level)
        ui.print_json([a.to_dict() for a in alerts])

    elif cmd == "drift":
        auditor = AgentAuditor()
        history = auditor.get_history(limit=100)
        if len(history) < 2:
            ui.warning("Need at least 2 audit records for drift detection.")
            return 1

        baseline = history[: args.baseline]
        current = history[-10:]
        detector = DriftDetector(threshold=args.threshold)
        reports = detector.detect_drift(baseline, current)

        tbl = ui.Table(box=ui.box.SIMPLE, header_style="bold yellow")
        tbl.add_column("Scanner", style="bold")
        tbl.add_column("Baseline", justify="right")
        tbl.add_column("Current", justify="right")
        tbl.add_column("Delta", justify="right")
        tbl.add_column("Status")
        for report in reports:
            status = "[red]DRIFTED[/]" if report.drifted else "[green]stable[/]"
            direction = "↓" if report.delta < 0 else "↑"
            delta_str = f"{direction}{abs(report.delta):.1f}"
            delta_color = "red" if report.drifted else "green"
            tbl.add_row(
                report.scanner_name,
                f"{report.baseline_score:.1f}",
                f"{report.current_score:.1f}",
                f"[{delta_color}]{delta_str}[/]",
                status,
            )
        ui._console().print(ui.Panel(tbl, title="Drift Detection Report", border_style="yellow"))

    else:
        ui.error("Unknown monitor command. Use: audit, history, alerts, drift")
        return 1

    return 0


def _cmd_redteam(args: Any) -> int:
    """Run red team security tests against a model."""
    from community_ai_audit.plugins.redteam import run_redteam_scanners
    from community_ai_audit.core.audit import AuditEngine

    engine = AuditEngine(
        config_path=getattr(args, "config", None),
        extra_plugin_paths=[],
    )

    adapter_config = _build_adapter_config(args, engine.config)
    provider = args.provider
    model_id = args.model

    ui.info(f"Loading model: {model_id} (provider: {provider}) ...")
    try:
        engine.load_model(model_id, provider=provider, adapter_config=adapter_config)
    except Exception as e:
        ui.error(f"Failed to load model: {e}")
        return 1

    ui.info("Running red team tests...")
    results = run_redteam_scanners(
        scanners=args.scanners,
        model=engine._model,
        adapter=engine._adapter,
    )

    if args.output == "json":
        ui.print_json(results)
    else:
        ui.print_results_table(
            results,
            title="Red Team Test Results",
            name_key="scanner_name",
            score_keys=["score"],
            extra_keys=["attack_success_rate", "total_attacks"],
        )

    return 0


def _cmd_mechinterp(args: Any) -> int:
    """Run mechanistic interpretability analysis."""
    from community_ai_audit.plugins.mechinterp import run_mechinterp_analyzers
    from community_ai_audit.core.audit import AuditEngine

    engine = AuditEngine(
        config_path=getattr(args, "config", None),
        extra_plugin_paths=[],
    )

    adapter_config = _build_adapter_config(args, engine.config)
    provider = args.provider
    model_id = args.model

    ui.info(f"Loading model: {model_id} (provider: {provider}) ...")
    try:
        engine.load_model(model_id, provider=provider, adapter_config=adapter_config)
    except Exception as e:
        ui.error(f"Failed to load model: {e}")
        return 1

    ui.info("Running mechanistic interpretability analysis...")
    results = run_mechinterp_analyzers(
        analyzers=args.analyzers,
        model=engine._model,
        adapter=engine._adapter,
    )

    if args.output == "json":
        ui.print_json(results)
    else:
        ui.print_results_table(
            results,
            title="Mechanistic Interpretability Results",
            name_key="interpreter_name",
            score_keys=["score"],
            extra_keys=["total_probes"],
        )

    return 0


def _cmd_alignment(args: Any) -> int:
    """Run alignment evaluation on a model."""
    from community_ai_audit.plugins.alignment import run_alignment_scanners
    from community_ai_audit.core.audit import AuditEngine

    engine = AuditEngine(
        config_path=getattr(args, "config", None),
        extra_plugin_paths=[],
    )

    adapter_config = _build_adapter_config(args, engine.config)
    provider = args.provider
    model_id = args.model

    ui.info(f"Loading model: {model_id} (provider: {provider}) ...")
    try:
        engine.load_model(model_id, provider=provider, adapter_config=adapter_config)
    except Exception as e:
        ui.error(f"Failed to load model: {e}")
        return 1

    ui.info("Running alignment evaluation...")
    results = run_alignment_scanners(
        scanners=args.scanners,
        model=engine._model,
        adapter=engine._adapter,
    )

    if args.output == "json":
        ui.print_json(results)
    else:
        ui.print_results_table(
            results,
            title="Alignment Evaluation Results",
            name_key="scanner_name",
            score_keys=["alignment_score", "score"],
            extra_keys=["confidence"],
        )

    return 0


def _cmd_audit_score(args: Any) -> int:
    """Compute unified audit score from result files."""
    from community_ai_audit.core.scoring import ScoringEngine

    def _load_json(path: str) -> list:
        if not path:
            return []
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, list) else [data]

    scan_results = _load_json(args.scan)
    policy_results = _load_json(args.policy)
    reliability_results = _load_json(args.reliability)
    agent_results = _load_json(args.agent)
    red_team_results = _load_json(args.redteam)
    alignment_results = _load_json(args.alignment)
    interpretability_results = _load_json(args.mechinterp)

    weights = None
    if hasattr(args, "weights") and args.weights:
        try:
            weights = {dim: float(val) for dim, val in args.weights}
        except ValueError as e:
            ui.error(f"Invalid weight: {e}")
            return 1

    engine = ScoringEngine(weights=weights)
    risk = engine.compute(
        scan_results=scan_results,
        policy_results=policy_results,
        reliability_results=reliability_results,
        agent_results=agent_results,
        red_team_results=red_team_results,
        alignment_results=alignment_results,
        interpretability_results=interpretability_results,
    )

    if args.output == "json":
        ui.print_json(risk.to_dict())
    else:
        dims = [
            ("Security", risk.security_score),
            ("Reliability", risk.reliability_score),
            ("Compliance", risk.compliance_score),
            ("Agent Risk", risk.agent_risk_score),
            ("Alignment", risk.alignment_score),
            ("Red Team", risk.red_team_score),
            ("Interpretability", risk.interpretability_score),
        ]
        ui.print_overall_score(risk.overall_score, *dims)
        ui.divider()
        ui.info(f"Weights: {risk.weights}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
