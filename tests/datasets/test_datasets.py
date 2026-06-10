"""Tests for benchmark datasets."""

import unittest
import tempfile
from pathlib import Path

from community_ai_audit.datasets.registry import (
    get_dataset,
    list_datasets,
    load_custom_dataset,
    record_benchmark_run,
    get_benchmark_history,
)
from community_ai_audit.datasets.models import BenchmarkRun


class TestBuiltinSafetyDataset(unittest.TestCase):
    def test_safety_dataset_registered(self):
        ds = get_dataset("safety", version="latest")
        self.assertIsNotNone(ds)
        self.assertEqual(ds["name"], "safety")
        self.assertIn("samples", ds)
        self.assertGreater(len(ds["samples"]), 0)

    def test_safety_samples_have_required_fields(self):
        ds = get_dataset("safety")
        for sample in ds["samples"]:
            self.assertIn("prompt", sample)
            self.assertIn("expected", sample)
            self.assertIn("category", sample)

    def test_safety_categories(self):
        ds = get_dataset("safety")
        categories = set(s["category"] for s in ds["samples"])
        self.assertIn("harmful", categories)
        self.assertIn("illegal", categories)
        self.assertIn("unethical", categories)


class TestBuiltinFactualityDataset(unittest.TestCase):
    def test_factuality_dataset_registered(self):
        ds = get_dataset("factuality")
        self.assertIsNotNone(ds)
        self.assertEqual(ds["name"], "factuality")
        self.assertGreater(len(ds["samples"]), 0)

    def test_factuality_samples_have_required_fields(self):
        ds = get_dataset("factuality")
        for sample in ds["samples"]:
            self.assertIn("prompt", sample)
            self.assertIn("expected", sample)
            self.assertIn("category", sample)

    def test_factuality_categories(self):
        ds = get_dataset("factuality")
        categories = set(s["category"] for s in ds["samples"])
        self.assertIn("science", categories)
        self.assertIn("history", categories)
        self.assertIn("geography", categories)
        self.assertIn("general", categories)


class TestDatasetRegistration(unittest.TestCase):
    def test_list_datasets(self):
        datasets = list_datasets()
        names = [ds.name for ds in datasets]
        self.assertIn("safety", names)
        self.assertIn("factuality", names)

    def test_get_dataset_versioning(self):
        # Test that 'latest' returns something
        ds = get_dataset("safety", version="latest")
        self.assertIsNotNone(ds)

    def test_get_nonexistent_dataset(self):
        ds = get_dataset("does-not-exist")
        self.assertIsNone(ds)


class TestCustomDataset(unittest.TestCase):
    def test_load_json_dataset(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            import json

            data = {
                "name": "my-custom-ds",
                "version": "0.1",
                "description": "Test custom dataset",
                "samples": [
                    {"prompt": "What is 1+1?", "expected": "2", "category": "math"},
                    {"prompt": "What is 2+2?", "expected": "4", "category": "math"},
                ],
            }
            json.dump(data, f)
            f.flush()
            ds = load_custom_dataset(f.name)
            self.assertEqual(ds.name, "my-custom-ds")
            self.assertEqual(ds.version, "0.1")
            samples = ds.load()
            self.assertEqual(len(samples), 2)
            Path(f.name).unlink()

    def test_load_jsonl_dataset(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            import json

            f.write(json.dumps({"prompt": "Q1", "expected": "A1"}) + "\n")
            f.write(json.dumps({"prompt": "Q2", "expected": "A2"}) + "\n")
            f.flush()
            ds = load_custom_dataset(f.name)
            samples = ds.load()
            self.assertEqual(len(samples), 2)
            Path(f.name).unlink()

    def test_load_yaml_dataset(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""name: yaml-ds
version: "1.0"
samples:
  - prompt: "Test?"
    expected: "Answer"
    category: general
""")
            f.flush()
            ds = load_custom_dataset(f.name)
            self.assertEqual(ds.name, "yaml-ds")
            samples = ds.load()
            self.assertEqual(len(samples), 1)
            Path(f.name).unlink()


class TestBenchmarkRun(unittest.TestCase):
    def test_benchmark_run_record_and_retrieve(self):
        import uuid

        run_id = f"test-run-{uuid.uuid4().hex[:8]}"
        run = BenchmarkRun(
            run_id=run_id,
            dataset_name="safety",
            dataset_version="1.0.0",
            model_id="test-model",
            adapter_name="test",
            accuracy=0.85,
            scores={"accuracy": 0.85},
            num_samples=10,
            num_passed=8,
            num_failed=2,
            duration_seconds=5.0,
        )
        record_benchmark_run(run)
        history = get_benchmark_history(dataset_name="safety", model_id="test-model")
        self.assertGreater(len(history), 0)
        found = [r for r in history if r.run_id == run_id]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].accuracy, 0.85)

    def test_benchmark_run_to_dict(self):
        run = BenchmarkRun(
            run_id="r1",
            dataset_name="d",
            dataset_version="1.0",
            model_id="m",
            adapter_name="a",
            accuracy=0.9,
            scores={"accuracy": 0.9},
            num_samples=10,
            num_passed=9,
            num_failed=1,
        )
        d = run.to_dict()
        self.assertEqual(d["run_id"], "r1")
        self.assertEqual(d["accuracy"], 0.9)
        self.assertEqual(d["num_passed"], 9)
