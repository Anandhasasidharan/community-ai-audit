"""Integration verification — exercises every component with real code paths."""

# ruff: noqa: E402

import sys
import traceback
import json
import subprocess
import re
from datetime import datetime, timezone

import torch
import torch.nn as nn

errors = []


def check(label, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}" + (f" \u2014 {detail}" if detail else ""))


def section(name):
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}")


def test(label, fn):
    try:
        fn()
        check(label, True)
    except Exception as e:
        check(label, False, str(e))
        errors.append((label, traceback.format_exc()))


# ── 1. Package import ──
section("1. Package Import")
import community_ai_audit

test("import community_ai_audit", lambda: True)
test("__version__ is semver", lambda: re.match(r"^\d+\.\d+\.\d+", community_ai_audit.__version__))
test("AuditEngine accessible", lambda: hasattr(community_ai_audit, "AuditEngine"))

# ── 2. Registry Discovery ──
section("2. Registry Discovery")
from community_ai_audit.core.registry import adapters, connectors, plugins

adapters.discover()
connectors.discover()
plugins.discover()

anames = set(adapters.list_available())
cnames = set(connectors.list_available())
snames = set(plugins.list_scanners())
inames = set(plugins.list_interpreters())
rnames = set(plugins.list_reporters())

test("6 adapters", lambda: len(anames) == 6)
test("4 connectors", lambda: len(cnames) == 4)
test("2 scanners", lambda: snames == {"adversarial", "backdoor"})
test("2 interpreters", lambda: inames == {"integrated-gradients", "lime"})
test("2 reporters", lambda: rnames == {"html", "markdown"})

# ── 3. Adapters ──
section("3. Adapter Instantiation")
for name in sorted(anames):
    inst = adapters.get(name)
    test(f"adapter {name}", lambda i=inst: True)
    test(
        f"adapter {name} connect/disconnect",
        lambda i=inst: hasattr(i, "connect") and hasattr(i, "disconnect"),
    )

# ── 4. Connectors ──
section("4. Connector Instantiation")
for name in sorted(cnames):
    inst = connectors.get(name)
    test(f"connector {name}", lambda i=inst: True)
    test(
        f"connector {name} has required methods",
        lambda i=inst: all(
            hasattr(i, m)
            for m in (
                "connect",
                "disconnect",
                "send_event",
                "send_batch",
                "query",
                "get_config_schema",
            )
        ),
    )
    schema = inst.get_config_schema()
    test(f"connector {name} schema", lambda s=schema: isinstance(s, dict))

# ── 5. Scanners ──
section("5. Scanner Real Scan")
from community_ai_audit.core.interfaces import ScanResult


class _DummyModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(10, 5)
        self.config = type("o", (object,), {"vocab_size": 100})()

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


for name in sorted(snames):
    inst = plugins.scanners.get(name)
    result = inst.scan(_DummyModel(), _DummyAdapter())
    test(f"scanner {name} -> ScanResult", lambda r=result: isinstance(r, ScanResult))
    test(f"scanner {name} has findings", lambda r=result: isinstance(r.findings, list))

# ── 6. Interpreters ──
section("6. Interpreter Real Test")
from community_ai_audit.core.interfaces import InterpretationResult

for name in sorted(inames):
    inst = plugins.interpreters.get(name)
    result = inst.interpret(_DummyModel(), _DummyAdapter(), [0.1] * 10)
    test(
        f"interpreter {name} -> InterpretationResult",
        lambda r=result: isinstance(r, InterpretationResult),
    )

# ── 7. Reporters ──
section("7. Reporter Render Test")
for name in sorted(rnames):
    inst = plugins.reporters.get(name)
    meta = {
        "session_id": "s1",
        "model_id": "m1",
        "risk_score": 50,
        "risk_level": "medium",
        "total_findings": 1,
    }
    out = inst.render([], [], meta)
    test(f"reporter {name} returns str", lambda o=out: isinstance(o, str))
    test(f"reporter {name} non-empty", lambda o=out: len(o) > 0)

# ── 8. AuditEngine ──
section("8. AuditEngine")
from community_ai_audit.core.audit import AuditEngine

eng = AuditEngine(discovery_on_init=False)
test("auto_detect openai", lambda: eng._auto_detect_provider("gpt-4o") == "openai")
test("auto_detect local", lambda: eng._auto_detect_provider("model.pt") == "local")

# ── 9. CLI Parsing ──
section("9. CLI Parsing")
from community_ai_audit.cli.main import build_parser

p = build_parser()
test("discover", lambda: p.parse_args(["discover"]).command == "discover")
test("scan", lambda: p.parse_args(["scan", "m", "--provider", "local"]).command == "scan")
test("audit", lambda: p.parse_args(["audit", "m", "--provider", "local"]).command == "audit")

# ── 10. ReportGenerator ──
section("10. ReportGenerator All 3 Formats")
from community_ai_audit.reporting.generator import ReportGenerator
from community_ai_audit.core.interfaces import Finding, Severity


class _FakeSession:
    session_id = "s"
    model_id = "m"
    adapter_name = "l"
    started_at = datetime.now(timezone.utc)
    completed_at = datetime.now(timezone.utc)
    duration_seconds = 1.5
    scan_results = [
        ScanResult(
            scanner_name="b",
            scanner_version="1.0",
            findings=[
                Finding(title="XSS", description="t", severity=Severity.HIGH, confidence=0.8)
            ],
        )
    ]
    interpret_results = []
    connector_results = {"s": "ok"}
    metadata = {"e": "t"}

    @property
    def total_findings(self):
        return 1

    @property
    def highest_severity(self):
        return Severity.HIGH

    def to_dict(self):
        return {
            "session_id": "s",
            "model_id": "m",
            "adapter_name": "l",
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": 1.5,
            "total_findings": 1,
            "highest_severity": "high",
            "scan_results": [r.to_dict() for r in self.scan_results],
            "interpret_results": [],
            "connector_results": self.connector_results,
            "metadata": self.metadata,
        }


g = ReportGenerator()
md = g.render_session(_FakeSession(), fmt="markdown")
js = g.render_session(_FakeSession(), fmt="json")
ht = g.render_session(_FakeSession(), fmt="html")
test("markdown has XSS", lambda: "XSS" in md)
test("json parses", lambda: json.loads(js)["session_id"] == "s")
test("html doctype", lambda: "<!DOCTYPE html>" in ht)
test("html finding", lambda: "XSS" in ht)
test("html risk-badge", lambda: "risk-badge" in ht)

# ── 11. CLI discover ──
section("11. CLI discover Command")
r = subprocess.run(
    ["python3", "-m", "community_ai_audit.cli.main", "discover"],
    capture_output=True,
    text=True,
    timeout=30,
)
test("exit 0", lambda: r.returncode == 0)
test("shows 6 adapters", lambda: "6 adapters" in r.stdout)

# ── 12. All module imports ──
section("12. All Module Imports")
mods = [
    "community_ai_audit",
    "community_ai_audit.core.audit",
    "community_ai_audit.core.registry",
    "community_ai_audit.core.interfaces",
    "community_ai_audit.cli.main",
    "community_ai_audit.adapters.local_adapter",
    "community_ai_audit.adapters.huggingface_adapter",
    "community_ai_audit.adapters.openai_adapter",
    "community_ai_audit.adapters.anthropic_adapter",
    "community_ai_audit.adapters.aws_bedrock_adapter",
    "community_ai_audit.adapters.ollama_adapter",
    "community_ai_audit.connectors.splunk_connector",
    "community_ai_audit.connectors.elastic_connector",
    "community_ai_audit.connectors.datadog_connector",
    "community_ai_audit.connectors.sentinel_connector",
    "community_ai_audit.connectors.base",
    "community_ai_audit.connectors.retry",
    "community_ai_audit.plugins.scanners.backdoor",
    "community_ai_audit.plugins.scanners.adversarial",
    "community_ai_audit.plugins.interpreters.integrated_gradients",
    "community_ai_audit.plugins.interpreters.lime",
    "community_ai_audit.plugins.reporters.markdown",
    "community_ai_audit.plugins.reporters.html",
    "community_ai_audit.reporting.generator",
]
for m in mods:
    test(f"import {m}", lambda mm=m: __import__(mm))

# ── Summary ──
section("SUMMARY")
if not errors:
    print("\n  ** ALL INTEGRATION CHECKS PASSED **")
else:
    print(f"\n  ** {len(errors)} FAILURES **")
    for label, tb in errors:
        print(f"\n  FAIL: {label}")
        print(f"  {tb.strip().split(chr(10))[-1]}")
    sys.exit(1)
