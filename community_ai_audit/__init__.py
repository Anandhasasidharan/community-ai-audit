"""
Community AI Security Audit Tool — Plugin-driven AI security auditing framework.

Usage:
    from community_ai_audit import AuditEngine
    engine = AuditEngine()
    engine.load_model("meta-llama/Llama-3-8B-Instruct", provider="huggingface")
    results = engine.audit(scanners=["backdoor", "adversarial"])
    print(results[0].summary())

Evaluation Framework:
    from community_ai_audit.core.evaluation import EvaluationEngine
    eval_engine = EvaluationEngine()
    result = eval_engine.evaluate("gpt-4", provider="openai", scanners=["adversarial"], policies=["no-pii-leakage"])
    benchmark = eval_engine.benchmark("gpt-4", provider="openai", dataset_name="safety")
    report = eval_engine.regression(baseline, current)
"""

__version__ = "0.5.1"
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
