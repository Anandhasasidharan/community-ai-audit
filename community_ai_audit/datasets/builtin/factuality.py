from __future__ import annotations

from typing import Any, Dict, List

from community_ai_audit.datasets.base import Dataset
from community_ai_audit.datasets.registry import register_dataset


class FactualityDataset(Dataset):
    """Built-in factuality benchmark dataset.

    Tests model accuracy on verifiable factual questions across domains:
    - science
    - history
    - geography
    - general knowledge
    """

    name = "factuality"
    description = "Built-in factuality benchmark: accuracy on verifiable factual questions"
    version = "1.0.0"
    categories = ["science", "history", "geography", "general"]

    SAMPLES = [
        # -- science --
        {
            "prompt": "What is the chemical symbol for gold?",
            "expected": "Au",
            "category": "science",
            "difficulty": "easy",
        },
        {
            "prompt": "What planet is known as the Red Planet?",
            "expected": "Mars",
            "category": "science",
            "difficulty": "easy",
        },
        {
            "prompt": "What is the speed of light in meters per second?",
            "expected": "299792458",
            "category": "science",
            "difficulty": "medium",
        },
        {
            "prompt": "Who proposed the theory of evolution by natural selection?",
            "expected": "Charles Darwin",
            "category": "science",
            "difficulty": "easy",
        },
        {
            "prompt": "What is the atomic number of carbon?",
            "expected": "6",
            "category": "science",
            "difficulty": "medium",
        },
        {
            "prompt": "What force keeps planets in orbit around the sun?",
            "expected": "gravity",
            "category": "science",
            "difficulty": "easy",
        },
        # -- history --
        {
            "prompt": "What year did World War II end?",
            "expected": "1945",
            "category": "history",
            "difficulty": "easy",
        },
        {
            "prompt": "Who was the first President of the United States?",
            "expected": "George Washington",
            "category": "history",
            "difficulty": "easy",
        },
        {
            "prompt": "In what year did the Titanic sink?",
            "expected": "1912",
            "category": "history",
            "difficulty": "easy",
        },
        {
            "prompt": "Who wrote the Declaration of Independence?",
            "expected": "Thomas Jefferson",
            "category": "history",
            "difficulty": "medium",
        },
        {
            "prompt": "What ancient civilization built Machu Picchu?",
            "expected": "Inca",
            "category": "history",
            "difficulty": "medium",
        },
        # -- geography --
        {
            "prompt": "What is the capital of France?",
            "expected": "Paris",
            "category": "geography",
            "difficulty": "easy",
        },
        {
            "prompt": "What is the longest river in the world?",
            "expected": "Nile",
            "category": "geography",
            "difficulty": "easy",
        },
        {
            "prompt": "Which country has the largest population?",
            "expected": "India",
            "category": "geography",
            "difficulty": "easy",
        },
        {
            "prompt": "What is the largest desert on Earth?",
            "expected": "Antarctic Desert",
            "category": "geography",
            "difficulty": "medium",
        },
        {
            "prompt": "How many continents are there?",
            "expected": "7",
            "category": "geography",
            "difficulty": "easy",
        },
        # -- general --
        {
            "prompt": "What is the largest mammal on Earth?",
            "expected": "blue whale",
            "category": "general",
            "difficulty": "easy",
        },
        {
            "prompt": "Who painted the Mona Lisa?",
            "expected": "Leonardo da Vinci",
            "category": "general",
            "difficulty": "easy",
        },
        {
            "prompt": "What is the most spoken language in the world?",
            "expected": "Mandarin Chinese",
            "category": "general",
            "difficulty": "medium",
        },
        {
            "prompt": "What is the boiling point of water in Celsius?",
            "expected": "100",
            "category": "general",
            "difficulty": "easy",
        },
        {
            "prompt": "How many bones are in the adult human body?",
            "expected": "206",
            "category": "general",
            "difficulty": "medium",
        },
    ]

    def load(self) -> List[Dict[str, Any]]:
        return list(self.SAMPLES)


register_dataset(FactualityDataset())
