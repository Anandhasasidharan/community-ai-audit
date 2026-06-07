"""
Custom scanner DSL — define scanners declaratively via YAML.

Enables users to create custom scanners without writing Python code.
Scanners are defined as YAML files with probes, checks, and severity rules.

Schema:
  name: str                # Scanner name (required)
  description: str         # Human-readable description
  version: str             # Semver string, default "0.1.0"
  probes:
    - input: str           # Prompt or input to send
      expected: str        # Optional expected output prefix
      checks:
        - type: contains   # Check types: contains, regex, length, not_contains
          value: str       # Value to check against
          severity: str    # Severity if check passes (critical/high/medium/low/info)
          confidence: float # 0.0-1.0
  severity_thresholds:
    critical: 0.8
    high: 0.6
    medium: 0.3
    low: 0.1

Usage:
  from community_ai_audit.plugins.scanners.dsl import load_dsl_scanner
  scanner = load_dsl_scanner("path/to/scanner.yaml")
  result = scanner.scan(model, adapter)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from community_ai_audit.core.interfaces import (
    ScannerPlugin,
    Finding,
    ScanResult,
    Severity,
    ModelAdapter,
)

log = logging.getLogger(__name__)


class DslScanner(ScannerPlugin):
    """Scanner defined via YAML DSL. Proxies all behavioral configuration
    from the loaded YAML definition.
    """

    name = "dsl_scanner"
    description = "DSL-defined scanner"
    version = "0.1.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._definition: Dict[str, Any] = {}
        self._probes: List[Dict[str, Any]] = []

    def load_definition(self, definition: Dict[str, Any]) -> None:
        self._definition = definition
        self.name = definition.get("name", "dsl_scanner")
        self.description = definition.get("description", "DSL-defined scanner")
        self.version = definition.get("version", "0.1.0")
        self._probes = definition.get("probes", [])

    def scan(
        self, model: Any, adapter: ModelAdapter, config: Optional[Dict[str, Any]] = None
    ) -> ScanResult:
        cfg = {**self.config, **(config or {})}
        thresholds = cfg.get(
            "severity_thresholds", self._definition.get("severity_thresholds", {})
        )
        findings: List[Finding] = []

        for probe in self._probes:
            try:
                input_text = probe.get("input", "")
                checks = probe.get("checks", [])
                expected_prefix = probe.get("expected", "")

                # Get model output
                output = self._run_probe(model, adapter, input_text, cfg)

                if not output:
                    continue

                output_str = str(output)

                # Check expected prefix
                if expected_prefix and not output_str.startswith(expected_prefix):
                    continue

                for check in checks:
                    finding = self._evaluate_check(
                        check, input_text, output_str, thresholds
                    )
                    if finding:
                        findings.append(finding)

            except Exception as e:
                log.warning("DSL probe '%s' failed: %s", probe.get("input", "")[:50], e)
                continue

        if not findings:
            findings.append(
                Finding(
                    title=f"DSL scanner '{self.name}' completed — no checks triggered",
                    description=f"All {len(self._probes)} probes passed their checks.",
                    severity=Severity.INFO,
                    confidence=0.5,
                )
            )

        return ScanResult(
            scanner_name=self.name,
            scanner_version=self.version,
            findings=findings,
            metadata={"definition": self._definition.get("name", self.name)},
        )

    def _run_probe(
        self, model: Any, adapter: ModelAdapter, input_text: str, cfg: Dict
    ) -> Any:
        if hasattr(adapter, "generate"):
            return adapter.generate(model, input_text)
        if hasattr(adapter, "predict"):
            result = adapter.predict(model, {"prompt": input_text})
            if hasattr(result, "choices"):
                return (
                    result.choices[0].message.content if result.choices else str(result)
                )
            return str(result)
        return None

    def _evaluate_check(
        self, check: Dict, input_text: str, output: str, thresholds: Dict
    ) -> Optional[Finding]:
        check_type = check.get("type", "contains")
        check_value = check.get("value", "")
        base_severity = check.get("severity", "medium")
        base_confidence = float(check.get("confidence", 0.5))

        triggered = False

        if check_type == "contains":
            triggered = check_value.lower() in output.lower()
        elif check_type == "not_contains":
            triggered = check_value.lower() not in output.lower()
        elif check_type == "regex":
            try:
                triggered = bool(re.search(check_value, output))
            except re.error:
                log.warning("Invalid regex in DSL: %s", check_value)
                return None
        elif check_type == "length":
            try:
                min_len = int(check.get("min", 0))
                max_len = int(check.get("max", 10**6))
                triggered = min_len <= len(output) <= max_len
            except (ValueError, TypeError):
                return None

        if not triggered:
            return None

        severity = self._resolve_severity(base_severity, thresholds)

        return Finding(
            title=f"DSL check triggered: {check_type}('{check_value}')",
            description=f"Input: '{input_text[:100]}...' triggered a '{check_type}' check "
            f"matching '{check_value}'.",
            severity=severity,
            confidence=base_confidence,
            evidence={
                "probe": input_text,
                "output_snippet": output[:200],
                "check": check,
            },
        )

    @staticmethod
    def _resolve_severity(base: str, thresholds: Dict) -> Severity:
        mapping = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
        }
        return mapping.get(base.lower(), Severity.MEDIUM)

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "severity_thresholds": {
                    "type": "object",
                    "properties": {
                        "critical": {"type": "number", "default": 0.8},
                        "high": {"type": "number", "default": 0.6},
                        "medium": {"type": "number", "default": 0.3},
                        "low": {"type": "number", "default": 0.1},
                    },
                },
            },
        }


def load_dsl_scanner(path: str) -> DslScanner:
    """Load a DSL scanner definition from a YAML file.

    Args:
        path: Path to YAML file.

    Returns:
        Configured DslScanner instance.
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"DSL scanner file not found: {p}")
    with open(p) as f:
        definition = yaml.safe_load(f) or {}
    if not isinstance(definition, dict):
        raise ValueError(f"Invalid DSL scanner format in {p}")
    if "name" not in definition:
        raise ValueError(f"DSL scanner missing required 'name' field in {p}")

    scanner = DslScanner()
    scanner.load_definition(definition)
    log.info("Loaded DSL scanner '%s' from %s", scanner.name, p)
    return scanner


def discover_dsl_scanners(directory: str = "scanners") -> List[DslScanner]:
    """Load all .yaml/.yml scanner definitions from a directory.

    Args:
        directory: Path to directory containing YAML scanner definitions.

    Returns:
        List of DslScanner instances.
    """
    scanners: List[DslScanner] = []
    d = Path(directory).expanduser().resolve()
    if not d.is_dir():
        log.warning("DSL scanner directory not found: %s", d)
        return scanners
    for f in sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")):
        try:
            scanners.append(load_dsl_scanner(str(f)))
        except Exception as e:
            log.error("Failed to load DSL scanner %s: %s", f, e)
    return scanners
