"""
Community AI Security Audit Tool — Plugin-driven AI security auditing framework.

Usage:
    from community_ai_audit import AuditEngine
    engine = AuditEngine()
    engine.load_model("meta-llama/Llama-3-8B-Instruct", provider="huggingface")
    results = engine.audit(scanners=["backdoor", "adversarial"])
    print(results[0].summary())

Plugins:
    Model Adapters — huggingface, openai, anthropic, aws_bedrock, local, ollama
    SIEM Connectors — splunk, elastic, datadog, sentinel
    Scanners — backdoor, adversarial
    Interpreters — integrated-gradients, lime
"""

__version__ = "0.2.0"
__author__ = "Community Contributors"

from community_ai_audit.cache import ModelCache
from community_ai_audit.core.audit import AuditEngine
from community_ai_audit.diff import AuditDiff, audit_diff
from community_ai_audit.core.interfaces import (
    ModelAdapter,
    SIEMConnector,
    SecurityToolConnector,
    ScannerPlugin,
    InterpreterPlugin,
    ReporterPlugin,
    Finding,
    ScanResult,
    InterpretationResult,
    Severity,
    ModelType,
)
from community_ai_audit.reporting import ReportGenerator

__all__ = [
    "AuditEngine",
    "AuditDiff",
    "audit_diff",
    "ModelCache",
    "ReportGenerator",
    "ModelAdapter",
    "SIEMConnector",
    "SecurityToolConnector",
    "ScannerPlugin",
    "InterpreterPlugin",
    "ReporterPlugin",
    "Finding",
    "ScanResult",
    "InterpretationResult",
    "Severity",
    "ModelType",
]
