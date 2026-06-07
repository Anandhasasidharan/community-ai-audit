"""
LRU cache with TTL for model predictions.

Thread-safe. Evicts least-recently-used entries when max_size is reached.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional, Tuple

log = logging.getLogger(__name__)


class ModelCache:
    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: float = 3600,
        enabled: bool = True,
    ):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled
        self._cache: OrderedDict[Tuple, Any] = OrderedDict()
        self._timestamps: Dict[Tuple, float] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: Tuple) -> Optional[Any]:
        if not self.enabled:
            return None
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            if time.time() - self._timestamps[key] > self.ttl_seconds:
                self._evict(key)
                self._misses += 1
                return None
            value = self._cache.pop(key)
            self._cache[key] = value
            self._hits += 1
            return value

    def set(self, key: Tuple, value: Any) -> None:
        if not self.enabled:
            return
        with self._lock:
            if len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                self._evict(oldest_key)
            self._cache[key] = value
            self._timestamps[key] = time.time()

    def _evict(self, key: Tuple) -> None:
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)
        self._evictions += 1

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def invalidate(self, key: Tuple) -> None:
        with self._lock:
            self._evict(key)

    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "enabled": self.enabled,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
                "evictions": self._evictions,
            }

    def make_predict_wrapper(self, predict_fn: Callable) -> Callable:
        def _wrapped(model: Any, inputs: Any, **kwargs) -> Any:
            if not self.enabled:
                return predict_fn(model, inputs, **kwargs)
            try:
                if isinstance(inputs, dict):
                    key = tuple(sorted((k, str(v)) for k, v in inputs.items()))
                elif isinstance(inputs, (list, tuple)):
                    key = tuple(str(x) for x in inputs)
                else:
                    key = (str(inputs),)
                if kwargs:
                    key = key + tuple(sorted((k, str(v)) for k, v in kwargs.items()))
            except (TypeError, ValueError):
                return predict_fn(model, inputs, **kwargs)

            cached = self.get(key)
            if cached is not None:
                log.debug("Cache hit for input key %s", str(key)[:80])
                return cached

            result = predict_fn(model, inputs, **kwargs)
            self.set(key, result)
            return result

        _wrapped.__wrapped__ = predict_fn
        return _wrapped
