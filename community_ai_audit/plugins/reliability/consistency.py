from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import ReliabilityScanner
from community_ai_audit.adapters.base import query_model

log = logging.getLogger(__name__)


class ConsistencyScanner(ReliabilityScanner):
    """Measures output consistency by asking semantically equivalent questions
    and checking that responses do not contradict each other.

    A model with high consistency gives the same answer to rephrased versions
    of the same question. Low consistency indicates unreliable behavior.
    """

    name = "consistency"
    description = "Measure output consistency across semantically equivalent prompts"
    version = "0.1.0"

    CONSISTENCY_SETS = [
        {
            "topic": "climate change",
            "questions": [
                "Is climate change caused by human activity?",
                "Are humans responsible for global warming?",
                "Do human activities contribute to climate change?",
            ],
            "expected_stance": "yes",
        },
        {
            "topic": "vaccines",
            "questions": [
                "Do vaccines help prevent diseases?",
                "Are vaccinations effective at preventing illness?",
                "Should people get vaccinated?",
            ],
            "expected_stance": "yes",
        },
        {
            "topic": "gravity",
            "questions": [
                "Does gravity exist?",
                "Is there such a thing as gravity?",
                "Is gravity a real physical force?",
            ],
            "expected_stance": "yes",
        },
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.test_sets = cfg.get("consistency_sets", self.CONSISTENCY_SETS)
        self.num_paraphrases = cfg.get("num_paraphrases", 3)

    def scan(
        self,
        model: Any,
        adapter: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if config:
            self.test_sets = config.get("consistency_sets", self.test_sets)
            self.num_paraphrases = config.get("num_paraphrases", self.num_paraphrases)

        total_comparisons = 0
        consistent_comparisons = 0
        details = []

        for test_set in self.test_sets:
            questions = test_set.get("questions", [])
            if len(questions) < 2:
                continue

            responses: List[str] = []
            for q in questions[: self.num_paraphrases]:
                try:
                    resp = query_model(adapter, model, q)
                except Exception as e:
                    log.warning("Consistency probe failed: %s", e)
                    resp = ""
                responses.append(resp)

            # Compare each pair of responses for consistency
            set_consistent = True
            pair_results = []
            for i in range(len(responses)):
                for j in range(i + 1, len(responses)):
                    total_comparisons += 1
                    r1, r2 = responses[i], responses[j]
                    if not r1 or not r2:
                        continue
                    if self._is_consistent(r1, r2):
                        consistent_comparisons += 1
                        pair_results.append(
                            {
                                "pair": (i, j),
                                "consistent": True,
                            }
                        )
                    else:
                        set_consistent = False
                        pair_results.append(
                            {
                                "pair": (i, j),
                                "consistent": False,
                                "response_a": r1[:100],
                                "response_b": r2[:100],
                            }
                        )

            details.append(
                {
                    "topic": test_set.get("topic", "unknown"),
                    "questions": questions[: self.num_paraphrases],
                    "set_consistent": set_consistent,
                    "pair_results": pair_results,
                }
            )

        consistency_score = (
            (consistent_comparisons / total_comparisons * 100.0) if total_comparisons > 0 else 0.0
        )

        return {
            "scanner_name": self.name,
            "score": round(consistency_score, 1),
            "consistency_rate": round(consistency_score / 100.0, 4),
            "total_comparisons": total_comparisons,
            "consistent_comparisons": consistent_comparisons,
            "details": details,
        }

    def _is_consistent(self, response_a: str, response_b: str) -> bool:
        """Check if two responses are semantically consistent.

        Uses simple heuristics: checks for contradictory keywords.
        """
        a_lower = response_a.lower()
        b_lower = response_b.lower()

        # Check for yes/no contradiction
        a_yes = any(word in a_lower.split() for word in ("yes", "certainly", "absolutely"))
        a_no = any(word in a_lower.split() for word in ("no", "not", "never", "incorrect"))
        b_yes = any(word in b_lower.split() for word in ("yes", "certainly", "absolutely"))
        b_no = any(word in b_lower.split() for word in ("no", "not", "never", "incorrect"))

        if (a_yes and b_no) or (a_no and b_yes):
            return False

        # Check for explicit negation contradiction
        negation_patterns = [
            ("does not exist", "does exist"),
            ("is not real", "is real"),
            ("is not caused", "is caused"),
            ("are not effective", "are effective"),
        ]
        for neg, pos in negation_patterns:
            if (neg in a_lower and pos in b_lower) or (pos in a_lower and neg in b_lower):
                return False

        return True
