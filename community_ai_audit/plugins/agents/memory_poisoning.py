from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .base import AgentScanner

log = logging.getLogger(__name__)


class MemoryPoisoningScanner(AgentScanner):
    """Detects memory poisoning or contamination in agent sessions.

    Analyzes memory write patterns for sensitive data exposure,
    prompt injection payloads, and abnormal memory operations.
    """

    name = "memory_poisoning"
    description = "Detect memory poisoning: sensitive data leaks, injection payloads, abnormal writes"
    version = "0.1.0"

    SENSITIVE_PATTERNS = [
        (re.compile(r"api[_-]?key[s]?[\s:=]+['\"]?[\w-]{16,}", re.I), "API key"),
        (re.compile(r"password[s]?[\s:=]+['\"]?\S+", re.I), "password"),
        (re.compile(r"secret[s]?[\s:=]+['\"]?\S+", re.I), "secret"),
        (re.compile(r"token[s]?[\s:=]+['\"]?\w{20,}", re.I), "token"),
        (re.compile(r"bearer\s+\w+", re.I), "bearer token"),
        (re.compile(r"sk-[a-zA-Z0-9]{20,}", re.I), "OpenAI API key"),
        (re.compile(r"ghp_[a-zA-Z0-9]{36}", re.I), "GitHub token"),
        (re.compile(r"AKIA[0-9A-Z]{16}", re.I), "AWS access key"),
        (re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"), "private key"),
    ]

    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
        re.compile(r"forget\s+(all\s+)?(your\s+)?(instructions|rules)", re.I),
        re.compile(r"system\s*(prompt|message|instruction)", re.I),
        re.compile(r"you\s+are\s+(now|not)\s+", re.I),
        re.compile(r"override\s+(your\s+)?(instructions|rules|configuration)", re.I),
        re.compile(r"act\s+as\s+(if\s+)?you\s+are", re.I),
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.sensitive_patterns = cfg.get(
            "sensitive_patterns", self.SENSITIVE_PATTERNS
        )
        self.injection_patterns = cfg.get(
            "injection_patterns", self.INJECTION_PATTERNS
        )
        self.max_memory_writes = cfg.get("max_memory_writes", 50)

    def scan(
        self,
        session: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if config:
            self.max_memory_writes = config.get("max_memory_writes", self.max_memory_writes)
            if "sensitive_patterns" in config:
                self.sensitive_patterns = [
                    (re.compile(p), l) if isinstance(p, str) else p
                    for p, l in config["sensitive_patterns"]
                ]
            if "injection_patterns" in config:
                self.injection_patterns = [
                    re.compile(p) if isinstance(p, str) else p
                    for p in config["injection_patterns"]
                ]

        findings: List[Dict[str, Any]] = []

        memory_writes = [
            s for s in session.steps
            if getattr(s, "step_type", None) is not None
            and s.step_type.value == "memory_access"
            and getattr(s, "input", {}).get("operation") == "write"
        ]

        total_writes = len(memory_writes)

        if total_writes > self.max_memory_writes:
            findings.append({
                "severity": "medium",
                "title": "Excessive memory writes",
                "description": (
                    f"{total_writes} memory writes exceeds "
                    f"limit of {self.max_memory_writes}"
                ),
                "total_writes": total_writes,
                "limit": self.max_memory_writes,
            })

        for mw in memory_writes:
            inp = mw.input if isinstance(mw.input, dict) else {}
            key = str(inp.get("key", ""))
            value = str(inp.get("value", "")) if inp.get("value") else str(mw.output if mw.output else "")

            combined = f"{key} {value}"

            for pattern, label in self.sensitive_patterns:
                if pattern.search(combined):
                    findings.append({
                        "severity": "high",
                        "title": f"Sensitive data in memory: {label}",
                        "description": (
                            f"Memory key '{key}' contains {label} pattern"
                        ),
                        "key": key,
                        "pattern_label": label,
                    })
                    break

            for pattern in self.injection_patterns:
                if pattern.search(combined):
                    findings.append({
                        "severity": "high",
                        "title": "Possible prompt injection payload in memory",
                        "description": (
                            f"Injection pattern detected in memory key '{key}'"
                        ),
                        "key": key,
                        "pattern": pattern.pattern[:60],
                    })
                    break

        memory_keys = []
        for mw in memory_writes:
            inp = mw.input if isinstance(mw.input, dict) else {}
            memory_keys.append(inp.get("key", "unknown"))

        score = self._compute_score(findings, total_writes)

        return {
            "scanner_name": self.name,
            "score": round(score, 1),
            "findings": findings,
            "details": {
                "total_memory_writes": total_writes,
                "sensitive_data_found": sum(
                    1 for f in findings if "Sensitive data" in f.get("title", "")
                ),
                "injection_payloads_found": sum(
                    1 for f in findings if "injection payload" in f.get("title", "")
                ),
                "finding_count": len(findings),
            },
        }

    def _compute_score(self, findings: List[Dict[str, Any]], total_writes: int) -> float:
        score = 100.0
        for f in findings:
            sev = f.get("severity", "low").lower()
            if sev == "critical":
                score -= 30
            elif sev == "high":
                score -= 20
            elif sev == "medium":
                score -= 10
            elif sev == "low":
                score -= 5
        return max(0.0, score)
