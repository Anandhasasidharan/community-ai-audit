from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import Dataset
from .models import DatasetInfo, BenchmarkRun

log = logging.getLogger(__name__)

# In-memory registry of built-in and custom datasets
_DATASETS: Dict[str, Dict[str, Dataset]] = {}  # name -> version -> Dataset
_BENCHMARK_HISTORY: List[BenchmarkRun] = []
_HISTORY_FILE = Path.home() / ".community-ai-audit" / "benchmark_history.json"


def register_dataset(dataset: Dataset, version: Optional[str] = None) -> None:
    """Register a dataset by name and version."""
    name = dataset.name
    ver = version or dataset.version
    if name not in _DATASETS:
        _DATASETS[name] = {}
    _DATASETS[name][ver] = dataset
    log.info("Registered dataset '%s' version '%s'", name, ver)


def get_dataset(name: str, version: str = "latest") -> Optional[Dict[str, Any]]:
    """Load and return a dataset's samples by name.

    Args:
        name: Dataset name.
        version: Version string, or 'latest' for the highest version.

    Returns:
        Dict with keys: samples, version, name, description, categories.
    """
    if name not in _DATASETS:
        log.warning("Dataset '%s' not found. Available: %s", name, list(_DATASETS.keys()))
        return None

    versions = _DATASETS[name]
    if version == "latest":
        # Pick the highest version string
        ver = sorted(versions.keys(), reverse=True)[0]
    elif version not in versions:
        log.warning(
            "Dataset '%s' version '%s' not found. Available: %s",
            name,
            version,
            list(versions.keys()),
        )
        return None
    else:
        ver = version

    dataset = versions[ver]
    samples = dataset.load()
    return {
        "samples": samples,
        "version": ver,
        "name": dataset.name,
        "description": dataset.description,
        "categories": dataset.categories,
    }


def list_datasets() -> List[DatasetInfo]:
    """List all registered datasets."""
    result = []
    for name, versions in _DATASETS.items():
        for ver, ds in versions.items():
            samples = ds.load()
            result.append(
                DatasetInfo(
                    name=name,
                    description=ds.description,
                    version=ver,
                    categories=ds.categories,
                    num_samples=len(samples),
                )
            )
    return result


def load_custom_dataset(path: str) -> Dataset:
    """Load a custom dataset from a JSON or JSONL file.

    Expected JSON format:
    ```json
    {
        "name": "my-dataset",
        "version": "1.0",
        "description": "...",
        "samples": [
            {"prompt": "...", "expected": "...", "category": "safety"}
        ]
    }
    ```
    """
    import yaml
    from .base import Dataset

    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    if p.suffix in {".json", ".jsonl"}:
        with open(p) as f:
            if p.suffix == ".json":
                data = json.load(f)
            else:
                lines = [json.loads(line) for line in f if line.strip()]
                data = {"samples": lines, "name": p.stem, "version": "1.0"}

        raw_samples = data.get("samples", [])
        ds_name = data.get("name", p.stem)
        ds_version = data.get("version", "1.0")
        ds_description = data.get("description", f"Custom dataset from {path}")
        ds_categories = list(
            set(s.get("category", "general") for s in raw_samples if "category" in s)
        )
        ds_samples = raw_samples

        def _make_json_dataset():
            class CustomDataset(Dataset):
                name = ds_name
                description = ds_description
                version = ds_version
                categories = ds_categories

                def load(self):
                    return ds_samples

            return CustomDataset()

        ds = _make_json_dataset()
        register_dataset(ds)
        return ds

    if p.suffix in {".yaml", ".yml"}:
        with open(p) as f:
            data = yaml.safe_load(f) or {}

        samples = data.get("samples", [])
        ds_name = data.get("name", p.stem)
        ds_version = data.get("version", "1.0")
        ds_description = data.get("description", f"Custom dataset from {path}")
        ds_categories = list(set(s.get("category", "general") for s in samples if "category" in s))
        ds_samples = samples

        def _make_yaml_dataset():
            class CustomYamlDataset(Dataset):
                name = ds_name
                description = ds_description
                version = ds_version
                categories = ds_categories

                def load(self):
                    return ds_samples

            return CustomYamlDataset()

        ds = _make_yaml_dataset()
        register_dataset(ds)
        return ds

    raise ValueError(f"Unsupported dataset format: {p.suffix}. Use .json, .jsonl, or .yaml.")


def record_benchmark_run(run: BenchmarkRun) -> None:
    """Persist a benchmark run for trend/regression analysis."""
    _load_history()
    _BENCHMARK_HISTORY.append(run)
    _save_history()


def get_benchmark_history(
    dataset_name: Optional[str] = None,
    model_id: Optional[str] = None,
    limit: int = 10,
) -> List[BenchmarkRun]:
    """Retrieve benchmark run history, optionally filtered."""
    _load_history()
    runs = list(_BENCHMARK_HISTORY)
    if dataset_name:
        runs = [r for r in runs if r.dataset_name == dataset_name]
    if model_id:
        runs = [r for r in runs if r.model_id == model_id]
    runs.sort(key=lambda r: r.timestamp, reverse=True)
    return runs[:limit]


def _load_history() -> None:
    """Load benchmark history from disk."""
    global _BENCHMARK_HISTORY
    if _BENCHMARK_HISTORY:
        return
    if _HISTORY_FILE.exists():
        try:
            with open(_HISTORY_FILE) as f:
                data = json.load(f)
            runs = []
            for item in data:
                if isinstance(item.get("timestamp"), str):
                    try:
                        item["timestamp"] = datetime.fromisoformat(item["timestamp"])
                    except (ValueError, TypeError):
                        item["timestamp"] = datetime.now(timezone.utc)
                runs.append(BenchmarkRun(**item))
            _BENCHMARK_HISTORY = runs
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Failed to load benchmark history: %s", e)
            _BENCHMARK_HISTORY = []


def _save_history() -> None:
    """Save benchmark history to disk."""
    _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = [r.to_dict() for r in _BENCHMARK_HISTORY]
    try:
        with open(_HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        log.warning("Failed to save benchmark history: %s", e)
