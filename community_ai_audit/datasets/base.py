from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class Dataset(ABC):
    """Abstract base for benchmark datasets.

    A dataset is a collection of test samples (prompts + expected outputs)
    used for benchmarking model performance.

    Datasets are versioned and can be filtered by category.
    """

    name: str = "base_dataset"
    description: str = ""
    version: str = "0.1.0"
    categories: List[str] = []

    @abstractmethod
    def load(self) -> List[Dict[str, Any]]:
        """Load all samples in the dataset.

        Each sample is a dict with at minimum:
            - prompt: str (input to the model)
            - expected: str (expected correct output)
        Optionally:
            - category: str
            - difficulty: str (easy, medium, hard)
            - metadata: dict
        """
        raise NotImplementedError

    def sample(
        self, limit: Optional[int] = None, category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Load and optionally filter samples."""
        all_samples = self.load()
        if category:
            all_samples = [s for s in all_samples if s.get("category") == category]
        if limit and limit < len(all_samples):
            all_samples = all_samples[:limit]
        return all_samples

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "categories": self.categories,
        }
