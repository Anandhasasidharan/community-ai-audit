"""Tests for the risk scoring engine."""

import unittest
from community_ai_audit.core.scoring import ScoringEngine, RiskScore


class TestScoringEngine(unittest.TestCase):
    def test_default_weights_sum_to_one(self):
        engine = ScoringEngine()
        total = sum(engine.weights.values())
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_custom_weights(self):
        engine = ScoringEngine(weights={"security": 0.5, "reliability": 0.3, "compliance": 0.2})
        total = sum(engine.weights.values())
        self.assertAlmostEqual(total, 1.0, places=6)
        # 4 missing dimensions get defaults (0.2, 0.2, 0.1, 0.1) = 0.6 + user-provided 1.0 = 1.6 total raw
        expected_security = 0.5 / 1.6
        self.assertAlmostEqual(engine.weights["security"], expected_security, places=4)

    def test_set_weight(self):
        engine = ScoringEngine()
        engine.set_weight("security", 0.6)
        # 7 dimensions: security=0.6, reliability=0.1, compliance=0.1,
        # agent_risk=0.2, alignment=0.2, red_team=0.1, interpretability=0.1 => raw total 1.4
        actual = engine.weights["security"]
        expected = 0.6 / 1.4
        self.assertAlmostEqual(actual, expected, places=4)
        self.assertAlmostEqual(sum(engine.weights.values()), 1.0, places=6)

    def test_set_weight_unknown_dimension(self):
        engine = ScoringEngine()
        with self.assertRaises(ValueError):
            engine.set_weight("unknown", 0.5)

    def test_compute_empty(self):
        engine = ScoringEngine()
        score = engine.compute()
        self.assertIsInstance(score, RiskScore)
        d = score.to_dict()
        for key in ("security_score", "reliability_score", "compliance_score",
                     "agent_risk_score", "alignment_score", "red_team_score",
                     "interpretability_score", "overall_score"):
            self.assertIn(key, d)

    def test_compute_high_security_findings(self):
        engine = ScoringEngine()
        scan_results = [
            {
                "findings": [
                    {"severity": "critical"},
                    {"severity": "critical"},
                    {"severity": "high"},
                    {"severity": "medium"},
                ]
            }
        ]
        score = engine.compute(scan_results=scan_results)
        # 2 criticals = -30, 1 high = -8, 1 medium = -3 => penalty 41
        self.assertLessEqual(score.security_score, 60)

    def test_compute_perfect_score(self):
        engine = ScoringEngine()
        score = engine.compute(
            scan_results=[{"findings": []}],
            policy_results=[{"status": "pass", "category": "security"}],
            reliability_results=[{"score": 95.0}],
        )
        self.assertGreater(score.overall_score, 80)

    def test_compute_compliance(self):
        engine = ScoringEngine()
        policy_results = [
            {"status": "pass", "category": "security"},
            {"status": "pass", "category": "security"},
            {"status": "fail", "category": "security"},
        ]
        score = engine.compute(policy_results=policy_results)
        self.assertGreater(score.compliance_score, 60)
        self.assertLess(score.compliance_score, 80)

    def test_risk_score_to_dict(self):
        score = RiskScore(
            security_score=85.0,
            reliability_score=72.0,
            compliance_score=91.0,
            agent_risk_score=80.0,
            alignment_score=90.0,
            red_team_score=75.0,
            interpretability_score=60.0,
            overall_score=83.0,
        )
        d = score.to_dict()
        self.assertEqual(d["security_score"], 85.0)
        self.assertEqual(d["reliability_score"], 72.0)
        self.assertEqual(d["compliance_score"], 91.0)
        self.assertEqual(d["agent_risk_score"], 80.0)
        self.assertEqual(d["alignment_score"], 90.0)
        self.assertEqual(d["red_team_score"], 75.0)
        self.assertEqual(d["interpretability_score"], 60.0)

    def test_interpret_overall(self):
        score = RiskScore(overall_score=95)
        self.assertEqual(score.interpret_overall(), "Excellent")
        score.overall_score = 82
        self.assertEqual(score.interpret_overall(), "Good")
        score.overall_score = 72
        self.assertEqual(score.interpret_overall(), "Fair")
        score.overall_score = 62
        self.assertEqual(score.interpret_overall(), "Poor")
        score.overall_score = 30
        self.assertEqual(score.interpret_overall(), "Critical")


class TestOverallAuditScore(unittest.TestCase):
    def test_creation(self):
        from community_ai_audit.core.scoring.models import OverallAuditScore
        score = OverallAuditScore(
            security=85.0, reliability=72.0, compliance=90.0,
            agent_risk=80.0, alignment=88.0, red_team=65.0,
            interpretability=55.0, overall=78.0,
        )
        d = score.to_dict()
        self.assertAlmostEqual(d["security"], 85.0)
        self.assertAlmostEqual(d["overall"], 78.0)

    def test_interpret(self):
        from community_ai_audit.core.scoring.models import OverallAuditScore
        self.assertEqual(OverallAuditScore(overall=95).interpret(), "Excellent")
        self.assertEqual(OverallAuditScore(overall=82).interpret(), "Good")
        self.assertEqual(OverallAuditScore(overall=72).interpret(), "Fair")
        self.assertEqual(OverallAuditScore(overall=62).interpret(), "Poor")
        self.assertEqual(OverallAuditScore(overall=40).interpret(), "Critical")


class TestRiskScore(unittest.TestCase):
    def test_min_max(self):
        score = RiskScore(
            security_score=90, reliability_score=50, compliance_score=70,
            agent_risk_score=80, alignment_score=60, red_team_score=40,
        )
        self.assertEqual(score.max_score, 90)
        self.assertEqual(score.min_score, 40)

    def test_audit_summary(self):
        score = RiskScore(overall_score=85.0, security_score=90, reliability_score=80,
                          compliance_score=85, agent_risk_score=88, alignment_score=82,
                          red_team_score=78, interpretability_score=65)
        summary = score.audit_summary()
        self.assertIn("Overall: 85.0", summary)
        self.assertIn("Alignment:", summary)
        self.assertIn("Red Team:", summary)
        self.assertIn("Interpretability:", summary)

    def test_scoring_with_redteam_results(self):
        engine = ScoringEngine()
        score = engine.compute(
            red_team_results=[
                {"scanner_name": "jailbreak", "score": 80.0, "attack_success_rate": 0.2, "total_attacks": 10, "successful_attacks": 2},
            ]
        )
        self.assertIsInstance(score.red_team_score, float)
        self.assertGreater(score.red_team_score, 0)

    def test_scoring_with_alignment_results(self):
        engine = ScoringEngine()
        score = engine.compute(
            alignment_results=[
                {"scanner_name": "sycophancy", "alignment_score": 85.0, "confidence": 0.9, "sycophancy_rate": 0.15},
            ]
        )
        self.assertIsInstance(score.alignment_score, float)
        self.assertGreater(score.alignment_score, 0)

    def test_scoring_with_interpretability_results(self):
        engine = ScoringEngine()
        score = engine.compute(
            interpretability_results=[
                {"interpreter_name": "activation_probes", "score": 72.0, "total_probes": 5},
            ]
        )
        self.assertIsInstance(score.interpretability_score, float)

    def test_scoring_all_new_dimensions(self):
        engine = ScoringEngine()
        score = engine.compute(
            red_team_results=[
                {"scanner_name": "jailbreak", "score": 80.0, "attack_success_rate": 0.2, "total_attacks": 10, "successful_attacks": 2},
            ],
            alignment_results=[
                {"scanner_name": "sycophancy", "alignment_score": 90.0, "confidence": 0.95, "sycophancy_rate": 0.1},
                {"scanner_name": "value_alignment", "score": 85.0, "alignment_score": 85.0, "confidence": 0.8},
            ],
            interpretability_results=[
                {"interpreter_name": "activation_probes", "score": 65.0, "total_probes": 5},
            ],
        )
        d = score.to_dict()
        self.assertIn("red_team_score", d)
        self.assertIn("alignment_score", d)
        self.assertIn("interpretability_score", d)
        self.assertGreater(score.overall_score, 0)

    def test_set_weight_alignment(self):
        engine = ScoringEngine()
        engine.set_weight("alignment", 0.5)
        self.assertAlmostEqual(sum(engine.weights.values()), 1.0, places=6)

    def test_set_weight_red_team(self):
        engine = ScoringEngine()
        engine.set_weight("red_team", 0.3)
        self.assertAlmostEqual(sum(engine.weights.values()), 1.0, places=6)

    def test_set_weight_interpretability(self):
        engine = ScoringEngine()
        engine.set_weight("interpretability", 0.3)
        self.assertAlmostEqual(sum(engine.weights.values()), 1.0, places=6)
