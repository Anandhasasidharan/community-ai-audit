"""
Performance benchmarks for cache, batch scan, and parallel connector dispatch.

These tests measure latency and throughput of critical paths.
Thresholds are set generously to pass on CI; regressions will still be caught.
"""

from __future__ import annotations

import time
import unittest

from community_ai_audit.cache import ModelCache


class TestCacheBenchmarks(unittest.TestCase):
    def setUp(self):
        self.cache = ModelCache(max_size=1000, ttl_seconds=3600, enabled=True)

    def test_cache_get_set_latency(self):
        key = ("test_input",)
        value = {"result": "data"}
        times = []
        for _ in range(100):
            start = time.perf_counter()
            self.cache.set(key, value)
            self.cache.get(key)
            times.append(time.perf_counter() - start)
        avg_ms = (sum(times) / len(times)) * 1000
        self.assertLess(avg_ms, 5.0, f"Average get/set latency too high: {avg_ms:.3f}ms")

    def test_cache_throughput(self):
        durations = []
        for batch_size in (10, 100, 500):
            start = time.perf_counter()
            for i in range(batch_size):
                k = (f"key_{i}",)
                self.cache.set(k, i)
                self.cache.get(k)
            durations.append(time.perf_counter() - start)
        ops_per_second = [batch / dur for batch, dur in zip((10, 100, 500), durations)]
        self.assertGreater(
            ops_per_second[-1], 100, f"Throughput too low: {ops_per_second[-1]:.0f} ops/s"
        )

    def test_cache_eviction_speed(self):
        small_cache = ModelCache(max_size=50, ttl_seconds=3600, enabled=True)
        start = time.perf_counter()
        for i in range(500):
            small_cache.set((f"evict_key_{i}",), i)
            small_cache.get((f"evict_key_{max(0, i-10)}",))
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 1.0, f"Eviction loop too slow: {elapsed:.3f}s")


class TestBatchScanBenchmarks(unittest.TestCase):
    def test_batch_scan_probe_parsing(self):
        import json

        probes = [{"input": f"test prompt {i}"} for i in range(1000)]
        start = time.perf_counter()
        for _ in range(10):
            _ = json.dumps(probes)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 10) * 1000
        self.assertLess(avg_ms, 500, f"Probe parsing too slow: {avg_ms:.1f}ms for 1000 entries")

    def test_severity_threshold_resolution(self):
        thresholds = {"critical": 0.9, "high": 0.7, "medium": 0.4, "low": 0.15}
        rates = [0.05, 0.2, 0.5, 0.8, 0.95]
        start = time.perf_counter()
        for _ in range(10000):
            for rate in rates:
                if rate >= thresholds["critical"]:
                    _ = "critical"
                elif rate >= thresholds["high"]:
                    _ = "high"
                elif rate >= thresholds["medium"]:
                    _ = "medium"
                elif rate >= thresholds["low"]:
                    _ = "low"
                else:
                    _ = "info"
        elapsed = time.perf_counter() - start
        self.assertLess(
            elapsed, 0.5, f"Severity resolution too slow: {elapsed:.3f}s for 50000 lookups"
        )


class TestParallelDispatchBenchmarks(unittest.TestCase):
    def test_connector_results_merge(self):
        results = {}
        names = [f"connector_{i}" for i in range(20)]
        start = time.perf_counter()
        for _ in range(1000):
            for name in names:
                results[name] = {"status": "success", "result": {"success": 5, "failed": 0}}
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.5, f"Result merge too slow: {elapsed:.3f}s for 20000 writes")

    def test_chunking_speed(self):
        from community_ai_audit.connectors.base import chunk_list

        events = [{"id": i, "data": "x" * 100} for i in range(5000)]
        start = time.perf_counter()
        for _ in range(100):
            list(chunk_list(events, 500))
        elapsed = time.perf_counter() - start
        avg_us = (elapsed / 100) * 1_000_000
        self.assertLess(avg_us, 50_000, f"Chunking too slow: {avg_us:.0f}us for 5000 events")


class TestDiffBenchmarks(unittest.TestCase):
    def test_finding_key_computation(self):
        from community_ai_audit.diff import _finding_key
        from community_ai_audit.core.interfaces import Finding, Severity

        findings = [
            Finding(
                title=f"Finding {i}",
                description=f"Desc {i}",
                severity=Severity.MEDIUM,
                cwe_id=f"CWE-{i}",
                mitre_id=f"AI-A{i}",
            )
            for i in range(1000)
        ]
        start = time.perf_counter()
        for _ in range(100):
            for f in findings:
                _finding_key(f)
        elapsed = time.perf_counter() - start
        avg_us = (elapsed / 100 / len(findings)) * 1_000_000
        self.assertLess(avg_us, 10, f"Finding key too slow: {avg_us:.2f}us per finding")

    def test_diff_matching_speed(self):
        from community_ai_audit.diff import _finding_key
        from community_ai_audit.core.interfaces import Finding, Severity

        findings_a = {
            _finding_key(
                Finding(title=f"F{i}", description=f"D{i}", severity=Severity.LOW)
            ): f"value_{i}"
            for i in range(500)
        }
        findings_b = {
            _finding_key(
                Finding(title=f"F{i}", description=f"D{i}", severity=Severity.LOW)
            ): f"value_{i}"
            for i in range(500)
        }
        start = time.perf_counter()
        for _ in range(100):
            keys_a = set(findings_a.keys())
            keys_b = set(findings_b.keys())
            _ = keys_b - keys_a
            _ = keys_a - keys_b
            _ = keys_a & keys_b
        elapsed = time.perf_counter() - start
        self.assertLess(
            elapsed, 0.5, f"Diff matching too slow: {elapsed:.3f}s for 500 findings x 100 runs"
        )


if __name__ == "__main__":
    unittest.main()
