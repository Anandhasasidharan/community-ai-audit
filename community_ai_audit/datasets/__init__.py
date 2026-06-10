# Auto-register built-in datasets on import
from . import builtin  # noqa: F401
from .base import Dataset
from .models import DatasetInfo, BenchmarkRun
from .registry import (
    register_dataset,
    get_dataset,
    list_datasets,
    load_custom_dataset,
    record_benchmark_run,
    get_benchmark_history,
)

__all__ = [
    "Dataset",
    "DatasetInfo",
    "BenchmarkRun",
    "register_dataset",
    "get_dataset",
    "list_datasets",
    "load_custom_dataset",
    "record_benchmark_run",
    "get_benchmark_history",
]
