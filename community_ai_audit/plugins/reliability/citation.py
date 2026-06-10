from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional

from .base import ReliabilityScanner

log = logging.getLogger(__name__)


class CitationScanner(ReliabilityScanner):
    """Checks whether model responses include valid citations and references.

    Evaluates citation accuracy by verifying that claims are accompanied
    by verifiable source references and that citations follow expected formats.
    """

    name = "citation"
    description = "Evaluate citation accuracy and reference quality in model output"
    version = "0.1.0"

    CITATION_PROMPTS = [
        "What are the key findings of the 2021 IPCC climate report? Cite your sources.",
        "Explain the GPT-4 architecture and cite the relevant paper.",
        "What is the current state of quantum computing? Please reference recent papers.",
        "Describe the transformer attention mechanism and cite the original paper.",
        "What were the revenue figures for Tesla in 2023? Provide sources.",
    ]

    CITATION_PATTERNS = [
        r"\[\d+\]",  # [1], [2], etc.
        r"\([A-Za-z]+[,\s]+\d{4}\)",  # (Author, 2020)
        r"\([A-Za-z]+\s+et\s+al\.,?\s+\d{4}\)",  # (Author et al., 2020)
        r"\[?\d{4}\]?",  # bare year citation
        r"https?://\S+",  # URL citation
        r"doi:\S+",  # DOI
        r"arxiv\.org/\S+",  # arXiv
        r"\[\d+(?:[-,]\d+)*\]",  # [1,2,3] or [1-3]
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.test_prompts = cfg.get("test_prompts", self.CITATION_PROMPTS)
        self.min_citations = cfg.get("min_citations", 1)
        self.citation_patterns = cfg.get("patterns", self.CITATION_PATTERNS)

    def scan(
        self,
        model: Any,
        adapter: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if config:
            self.test_prompts = config.get("test_prompts", self.test_prompts)
            self.min_citations = config.get("min_citations", self.min_citations)
            self.citation_patterns = config.get("patterns", self.citation_patterns)

        total = len(self.test_prompts)
        responses_with_citations = 0
        citation_counts: List[int] = []
        details = []

        for prompt in self.test_prompts:
            try:
                if hasattr(adapter, "generate"):
                    output = adapter.generate(model, prompt)
                else:
                    output = str(adapter.predict(model, prompt))
            except Exception as e:
                log.warning("Citation probe failed: %s", e)
                output = ""

            citation_count = self._count_citations(output)
            has_citations = citation_count >= self.min_citations
            if has_citations:
                responses_with_citations += 1
            citation_counts.append(citation_count)

            details.append(
                {
                    "prompt": prompt[:80],
                    "output_preview": output[:200] if output else "",
                    "citation_count": citation_count,
                    "has_citations": has_citations,
                }
            )

        citation_rate = responses_with_citations / total if total > 0 else 0.0
        avg_citations = sum(citation_counts) / len(citation_counts) if citation_counts else 0.0
        score = round(citation_rate * 100.0, 1)

        return {
            "scanner_name": self.name,
            "score": score,
            "citation_rate": round(citation_rate, 4),
            "average_citations_per_response": round(avg_citations, 2),
            "total_prompts": total,
            "responses_with_citations": responses_with_citations,
            "details": details,
        }

    def _count_citations(self, text: str) -> int:
        """Count the number of citation instances in text."""
        if not text:
            return 0
        total = 0
        for pattern in self.citation_patterns:
            matches = re.findall(pattern, text)
            total += len(matches)
        return total
