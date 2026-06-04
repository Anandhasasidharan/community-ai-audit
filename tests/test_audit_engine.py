"""Unit tests for AuditEngine orchestration."""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from community_ai_audit.core.audit import AuditEngine, AuditSession
from community_ai_audit.core.interfaces import (
    ScanResult, InterpretationResult, Finding, Severity,
)


class TestAuditEngine(unittest.TestCase):
    def test_load_model_and_audit_flow(self):
        engine = AuditEngine(discovery_on_init=True)
        with patch.object(engine, '_adapter', None), \
             patch.object(engine, '_model', None), \
             patch.object(engine, 'discover', lambda: None):
            # Mock adapter and plugins
            mock_adapter = MagicMock()
            mock_adapter.name = "huggingface"
            mock_adapter.get_model.return_value = MagicMock()
            mock_adapter.predict.return_value = {"outputs": [0.5]}
            mock_adapter.supports_model_type.return_value = True
            mock_adapter.get_input_spec.return_value = {"type": "text"}
            mock_adapter.tokenize.return_value = [1, 2, 3]
            mock_adapter.generate.return_value = "test"
            mock_adapter.get_logits.return_value = [0.1, 0.2]
            mock_adapter.get_attention_weights.return_value = [[0.3, 0.4]]
            engine._adapter = mock_adapter
            engine._model = MagicMock()

            # Mock scanner
            mock_scanner = MagicMock()
            mock_scanner.scan.return_value = ScanResult(
                scanner_name="mock-scanner",
                scanner_version="1.0",
                findings=[
                    Finding(title="Test", description="desc", severity=Severity.LOW, confidence=0.5)
                ],
            )

            # Mock interpreter
            mock_interpreter = MagicMock()
            mock_interpreter.interpret.return_value = InterpretationResult(
                interpreter_name="mock-interp",
                interpreter_version="1.0",
                attributions={"test": 0.5},
            )

            with patch('community_ai_audit.core.registry.plugins.scanners.get', return_value=mock_scanner), \
                 patch('community_ai_audit.core.registry.plugins.interpreters.get', return_value=mock_interpreter), \
                 patch('community_ai_audit.core.registry.plugins.list_scanners', return_value=["mock-scanner"]), \
                 patch('community_ai_audit.core.registry.plugins.list_interpreters', return_value=["mock-interp"]), \
                 patch.object(engine, 'discover', lambda: None):

                session = engine.audit(
                    scanners=["mock-scanner"],
                    interpreters=["mock-interp"],
                    inputs="test input",
                )

                self.assertIsInstance(session, AuditSession)
                self.assertEqual(session.total_findings, 1)
                self.assertEqual(len(session.scan_results), 1)
                self.assertEqual(len(session.interpret_results), 1)
                self.assertIsNotNone(session.started_at)
                self.assertIsNotNone(session.completed_at)
                self.assertGreater(session.duration_seconds, 0)

    def test_session_risk_calculation(self):
        session = AuditSession(
            session_id="test-1",
            model_id="test-model",
            adapter_name="test-adapter",
            started_at=datetime.utcnow(),
        )

        # No findings = low risk
        self.assertEqual(session.total_findings, 0)

        # Add findings
        session.scan_results = [
            ScanResult(
                scanner_name="s1",
                scanner_version="1.0",
                findings=[
                    Finding(title="F1", description="d", severity=Severity.HIGH, confidence=0.9),
                ],
            ),
            ScanResult(
                scanner_name="s2",
                scanner_version="1.0",
                findings=[
                    Finding(title="F2", description="d", severity=Severity.MEDIUM, confidence=0.7),
                ],
            ),
        ]
        self.assertEqual(session.total_findings, 2)
        self.assertEqual(session.highest_severity, Severity.HIGH)

    def test_session_to_dict(self):
        session = AuditSession(
            session_id="test-2",
            model_id="model",
            adapter_name="adapter",
            started_at=datetime.utcnow(),
        )
        d = session.to_dict()
        self.assertEqual(d["session_id"], "test-2")
        self.assertIn("total_findings", d)
        self.assertIn("highest_severity", d)

    def test_auto_detect_provider_heuristics(self):
        engine = AuditEngine(discovery_on_init=False)
        self.assertEqual(engine._auto_detect_provider("gpt-4o"), "openai")
        self.assertEqual(engine._auto_detect_provider("claude-3-opus"), "anthropic")
        self.assertEqual(engine._auto_detect_provider("meta-llama/Llama-3-8B"), "huggingface")
        self.assertEqual(engine._auto_detect_provider("model.pt"), "local")
        self.assertEqual(engine._auto_detect_provider("llama2"), "huggingface")
        self.assertEqual(engine._auto_detect_provider("mistral"), "huggingface")


if __name__ == "__main__":
    unittest.main()
