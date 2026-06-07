"""
Command-line interface for the community AI security audit tool.
Uses the plug-and-play AuditEngine under the hood.
"""

import argparse
import sys
import json
import os
import logging
from typing import Any, List, Optional

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

    # ── RBAC global flags ─────────────────────────────────────
    for sub in (sched_parser,):
        sub.add_argument("--user", help="Username for RBAC authentication")
        sub.add_argument(
            "--api-key-rbac", dest="rbac_api_key", help="API key for RBAC authentication"
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
        parser.print_help()
        return 1

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
        print(f"Access denied: {e}")
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
            print(f"Schedule '{args.name}' added (cron: {args.cron})")
        except Exception as e:
            print(f"Failed to add schedule: {e}")
            return 1

    elif cmd == "list":
        schedules = scheduler.list_schedules()
        if not schedules:
            print("No schedules configured.")
        else:
            for s in schedules:
                next_run = scheduler._get_next_run(s.get("cron", ""))
                print(
                    f"  {s['name']:20s} | cron: {s.get('cron', ''):15s} | "
                    f"model: {s.get('model_id', ''):30s} | "
                    f"next: {next_run or 'N/A'}"
                )
                print(f"  {'':20s} | scanners: {', '.join(s.get('scanners', [])) or '(all)'}")

    elif cmd == "remove":
        try:
            scheduler.remove_schedule(args.name)
            print(f"Schedule '{args.name}' removed.")
        except KeyError:
            print(f"Schedule '{args.name}' not found.")
            return 1

    elif cmd == "run":
        if args.name:
            all_schedules = scheduler.list_schedules()
            found = [s for s in all_schedules if s["name"] == args.name]
            if not found:
                print(f"Schedule '{args.name}' not found.")
                return 1
            schedules_to_run = [(found[0], scheduler._get_next_run(found[0].get("cron", "")))]
        else:
            schedules_to_run = scheduler.get_due_schedules()

        if not schedules_to_run:
            print("No schedules due.")
            return 0

        for sched, _ in schedules_to_run:
            print(f"Running schedule '{sched['name']}'...")
            try:
                results = scheduler.run_due(engine)
                if results:
                    for r in results:
                        print(f"  {r.get('name', '?'):20s} -> {r.get('status', '?')}")
                print(f"Schedule '{sched['name']}' completed.")
            except Exception as e:
                print(f"Schedule '{sched['name']}' failed: {e}")
                return 1

    else:
        print("Unknown schedule command. Use: add, list, remove, run")
        return 1

    return 0


def _cmd_discover(engine, args) -> int:
    """List all discovered plugins, adapters, and connectors."""

    caps = engine.list_capabilities()

    if args.format == "json":
        print(json.dumps(caps, indent=2))
    else:
        print("\n" + "─" * 60)
        print("🎛  Community AI Audit — Discovered Capabilities")
        print("─" * 60)

        for category, items in caps.items():
            print(f"\n  {category.replace('_', ' ').title()}:")
            for item in items:
                print(f"    • {item}")

    return 0


def _cmd_scan(engine, args) -> int:
    """Run scanners."""
    import json as _json
    from community_ai_audit.reporting import ReportGenerator

    try:
        _rbac_check(args)
    except (PermissionError, RBACPermError) as e:
        print(f"Access denied: {e}")
        return 1

    adapter_config = _build_adapter_config(args, engine.config)
    model_id = args.model

    print(f"Loading model: {model_id} (provider: {args.provider}) ...")
    engine.load_model(model_id, provider=args.provider, adapter_config=adapter_config)
    print("Model loaded. Running scanners...")

    selected_scanners, _selected_interpreters, profile_overrides = _apply_profile_defaults(
        profile=getattr(args, "profile", "standard"),
        scanners=args.scanners,
        interpreters=None,
    )
    scanner_overrides = _merge_overrides(profile_overrides, _build_scanner_overrides(args))
    results = engine.scan(scanners=selected_scanners, config_overrides=scanner_overrides)

    # Generate and print / save report
    reporter = ReportGenerator()
    if args.output == "json":
        report = _json.dumps([r.to_dict() for r in results], indent=2)
    else:
        report = reporter.render_scan_results(results, fmt=args.output)

    print(report)

    if args.save:
        _save_report(report, args.save)

    # Push to SIEM if requested
    if args.connectors:
        connector_configs = _build_connector_configs(args, engine.config)
        connector_results = engine._push_to_connectors(
            results, [], args.connectors, connector_configs
        )
        for name, status in connector_results.items():
            print(f"Connector {name}: {status}")

    # Exit with non-zero if critical/high/medium findings
    highest = max(
        (r.overall_severity for r in results),
        key=lambda s: _severity_rank(s),
        default=None,
    )
    if highest is None:
        return 0
    if getattr(highest, "value", str(highest)).lower() == "critical":
        return 2
    if getattr(highest, "value", str(highest)).lower() in ("high", "medium"):
        return 1
    return 0


def _cmd_interpret(engine, args) -> int:
    """Run interpreters."""
    import json as _json
    from community_ai_audit.reporting import ReportGenerator

    try:
        _rbac_check(args)
    except (PermissionError, RBACPermError) as e:
        print(f"Access denied: {e}")
        return 1

    adapter_config = _build_adapter_config(args, engine.config)
    model_id = args.model

    print(f"Loading model: {model_id} (provider: {args.provider}) ...")
    engine.load_model(model_id, provider=args.provider, adapter_config=adapter_config)
    print("Model loaded. Running interpreters...")

    raw_input = args.input_data or "Explain this model's decision for a neutral statement."
    inputs = _parse_input_value(raw_input)
    results = engine.interpret(
        inputs=inputs,
        interpreters=args.interpreters,
    )

    reporter = ReportGenerator()
    if args.output == "json":
        report = _json.dumps([r.to_dict() for r in results], indent=2)
    else:
        report = reporter.render_interpret_results(results, fmt=args.output)

    print(report)

    if args.save:
        _save_report(report, args.save)

    return 0


def _cmd_audit(engine, args) -> int:
    """Run full audit."""
    import json as _json
    from community_ai_audit.reporting import ReportGenerator

    try:
        _rbac_check(args)
    except (PermissionError, RBACPermError) as e:
        print(f"Access denied: {e}")
        return 1

    adapter_config = _build_adapter_config(args, engine.config)
    model_id = args.model

    print(f"Loading model: {model_id} (provider: {args.provider}) ...")
    engine.load_model(model_id, provider=args.provider, adapter_config=adapter_config)
    print("Model loaded. Running full audit...")

    selected_scanners, selected_interpreters, profile_overrides = _apply_profile_defaults(
        profile=getattr(args, "profile", "standard"),
        scanners=args.scanners,
        interpreters=args.interpreters,
    )

    parsed_inputs = _parse_input_value(args.input_data) if args.input_data else None
    scanner_overrides = _merge_overrides(profile_overrides, _build_scanner_overrides(args))
    run_metadata = _build_run_metadata(args, scanner_overrides)
    connector_configs = _build_connector_configs(args, engine.config)

    session = engine.audit(
        scanners=selected_scanners,
        interpreters=selected_interpreters,
        inputs=parsed_inputs if selected_interpreters else None,
        connectors=args.connectors,
        connector_configs=connector_configs,
        config_overrides=scanner_overrides,
        run_metadata=run_metadata,
    )

    # Generate report
    reporter = ReportGenerator()
    if args.output == "json":
        report = _json.dumps(session.to_dict(), indent=2, default=str)
    else:
        report = reporter.render_session(session, fmt=args.output)

    print(report)
    print("\n" + session.summary())

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


if __name__ == "__main__":
    sys.exit(main())
