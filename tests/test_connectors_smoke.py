"""Connector smoke tests with mocked network/client dependencies.

These tests validate connector behavior including retry logic, validation,
and DLQ fallback.
"""

import base64
import json
import sys
import types
import unittest
from unittest.mock import patch, MagicMock

import requests


class _FakeResp:
    def __init__(self, status_code=200, payload=None, raise_for_status=None):
        self.status_code = status_code
        self._payload = payload or {}
        self._raise = raise_for_status

    def raise_for_status(self):
        if self._raise:
            raise self._raise
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, resp_queue=None):
        self.headers = {}
        self.last_post = None
        self._resp_queue = list(resp_queue) if resp_queue else [_FakeResp(200, {"acknowledged": 1})]
        self._get_calls = 0
        self._post_calls = 0

    def get(self, *args, **kwargs):
        self._get_calls += 1
        if self._resp_queue:
            return self._resp_queue.pop(0)
        return _FakeResp(200)

    def post(self, *args, **kwargs):
        self._post_calls += 1
        self.last_post = (args, kwargs)
        if self._resp_queue:
            return self._resp_queue.pop(0)
        return _FakeResp(200, {"acknowledged": 1})


class _FakeRequestsModule:
    """Mock of the requests module."""
    def __init__(self, resp_queue=None):
        self._resp_queue = list(resp_queue) if resp_queue else [_FakeResp(200, {"acknowledged": 1})]
        self.Session = lambda: _FakeSession(self._resp_queue)  # return a factory that captures resp_queue

    def get(self, *args, **kwargs):
        if self._resp_queue:
            return self._resp_queue.pop(0)
        return _FakeResp(200)

    def post(self, *args, **kwargs):
        if self._resp_queue:
            return self._resp_queue.pop(0)
        return _FakeResp(200, {"acknowledged": 1})


class _FakeBulkResp:
    def __init__(self, errors=False, items=None):
        self.errors = errors
        self.items = items or []


class _FakeESClient:
    def __init__(self, bulk_resp=None, ping_ret=True):
        self.bulk_resp = bulk_resp or _FakeBulkResp(errors=False, items=[])
        self.ping_ret = ping_ret
        self.last_body = None

    def bulk(self, body=None, **kwargs):
        self.last_body = body
        return {"errors": self.bulk_resp.errors, "items": self.bulk_resp.items}

    def ping(self):
        return self.ping_ret

    def search(self, index=None, q=None, size=100):
        return {"hits": {"hits": [{"_source": {"mock": "hit"}}]}}


class TestConnectorsSmoke(unittest.TestCase):
    def test_splunk_connect_and_send_batch_success(self):
        from community_ai_audit.connectors.splunk_connector import SplunkConnector

        c = SplunkConnector()
        # Mock requests module at the connector level: first response for health check GET, second for POST
        with patch("community_ai_audit.connectors.splunk_connector.requests", _FakeRequestsModule([
            _FakeResp(200),  # health check GET
            _FakeResp(200, {"acknowledged": 2})  # POST for sending events
        ])):
            c.connect({"hec_url": "https://splunk.local:8088", "hec_token": "tok"})
            out = c.send_batch([
                {"title": "t1", "description": "d1", "severity": "high", "confidence": 0.8},
                {"title": "t2", "description": "d2", "severity": "medium", "confidence": 0.5},
            ])
            self.assertEqual(out["success"], 2)
            self.assertEqual(out["failed"], 0)

    def test_splunk_retry_on_5xx(self):
        from community_ai_audit.connectors.splunk_connector import SplunkConnector

        # First two attempts fail with 503, third succeeds
        # Also include health check GET in connect()
        resp_queue = [_FakeResp(200), _FakeResp(503), _FakeResp(503), _FakeResp(200, {"acknowledged": 2})]
        c = SplunkConnector()
        with patch("community_ai_audit.connectors.splunk_connector.requests.Session") as mock_session_class:
            mock_session_class.side_effect = lambda: _FakeSession(resp_queue)
            c.connect({"hec_url": "https://splunk.local:8088", "hec_token": "tok", "retry": {"max_attempts": 5}})
            out = c.send_batch([
                {"title": "t1", "description": "d1", "severity": "high"},
                {"title": "t2", "description": "d2", "severity": "low"},
            ])
            self.assertEqual(out["success"], 2)
            self.assertEqual(out["failed"], 0)

    def test_splunk_dlq_on_non_retryable_error(self):
        from community_ai_audit.connectors.splunk_connector import SplunkConnector
        import logging

        # 400 Bad Request -> not retryable -> should go to DLQ
        # Include health check GET in connect()
        resp_queue = [_FakeResp(200), _FakeResp(400)]
        c = SplunkConnector()
        with patch("community_ai_audit.connectors.splunk_connector.requests.Session") as mock_session_class:
            mock_session_class.side_effect = lambda: _FakeSession(resp_queue)
            with self.assertLogs(logging.getLogger(), level='ERROR') as cm:
                c.connect({"hec_url": "https://splunk.local:8088", "hec_token": "tok"})
                out = c.send_batch([{"title": "t1", "description": "d1", "severity": "high"}])
                self.assertEqual(out["success"], 0)
                self.assertEqual(out["failed"], 1)
                self.assertTrue(any("[DLQ]" in msg for msg in cm.output))

    def test_datadog_connect_and_send_batch_success(self):
        from community_ai_audit.connectors.datadog_connector import DatadogConnector

        c = DatadogConnector()
        # Mock requests where it's used inside the methods
        with patch("community_ai_audit.connectors.datadog_connector.requests") as mock_req:
            # First call: validation GET in connect (returns 200)
            # Second call: POST in send_batch (returns 202 Accepted)
            mock_req.get.return_value = _FakeResp(200)
            mock_req.post.return_value = _FakeResp(202)
            
            c.connect({"dd_api_key": "k", "dd_site": "datadoghq.com", "service": "ai-audit"})
            out = c.send_batch([
                {"title": "t", "description": "d", "severity": "medium", "confidence": 0.6}
            ])
            self.assertEqual(out["success"], 1)

    def test_datadog_retry_on_429_then_success(self):
        from community_ai_audit.connectors.datadog_connector import DatadogConnector

        c = DatadogConnector()
        with patch("community_ai_audit.connectors.datadog_connector.requests.post") as mock_post, \
             patch("community_ai_audit.connectors.datadog_connector.requests.get") as mock_get:
            # Queue for POST calls in send_batch: 429, 429, 202
            # First GET for validation returns 200
            mock_get.return_value = _FakeResp(200)
            mock_post.side_effect = [_FakeResp(429), _FakeResp(429), _FakeResp(202)]
            
            c.connect({"dd_api_key": "k", "dd_site": "datadoghq.com", "service": "ai-audit", "retry": {"max_attempts": 3}})
            out = c.send_batch([{"title": "t", "description": "d", "severity": "medium"}])
            self.assertEqual(out["success"], 1)
            self.assertEqual(mock_post.call_count, 3)

    def test_elastic_send_batch_with_mock_client_success(self):
        from community_ai_audit.connectors.elastic_connector import ElasticConnector

        c = ElasticConnector()
        c._client = _FakeESClient(_FakeBulkResp(errors=False, items=[{"index": {}}, {"index": {}}]))
        c._index = "security-ai-audit"

        out = c.send_batch([
            {"title": "a", "description": "d", "severity": "high", "confidence": 0.9},
            {"title": "b", "description": "d", "severity": "low", "confidence": 0.2},
        ])
        self.assertEqual(out["success"], 2)
        self.assertEqual(out["failed"], 0)

    def test_elastic_send_batch_with_item_errors(self):
        from community_ai_audit.connectors.elastic_connector import ElasticConnector
        import logging

        # First item succeeds, second fails
        c = ElasticConnector()
        c._client = _FakeESClient(_FakeBulkResp(errors=True, items=[
            {"index": {}},  # success
            {"index": {"error": {"type": "mapper_parsing_exception", "reason": "failed"}}},  # fail
        ]))
        c._index = "security-ai-audit"

        with self.assertLogs(logging.getLogger(), level='WARNING') as cm:
            out = c.send_batch([
                {"title": "ok", "description": "d", "severity": "high"},
                {"title": "bad", "description": "d", "severity": "low"},
            ])
            self.assertEqual(out["success"], 1)
            self.assertEqual(out["failed"], 1)
            self.assertTrue(any("mapper_parsing_exception" in msg for msg in cm.output))

    def test_sentinel_connect_and_send_batch_success(self):
        from community_ai_audit.connectors.sentinel_connector import SentinelConnector

        c = SentinelConnector()
        shared_key = base64.b64encode(b"secretkey").decode("utf-8")

        # Mock requests where it's used
        with patch("community_ai_audit.connectors.sentinel_connector.requests") as mock_req:
            # First call: validation GET in connect (returns 200)
            # Second call: POST in send_batch (returns 200)
            mock_req.get.return_value = _FakeResp(200)
            mock_req.post.return_value = _FakeResp(200)
            
            c.connect({
                "workspace_id": "workspace123",
                "shared_key": shared_key,
                "log_type": "AIAudit",
            })
            out = c.send_batch([
                {"title": "t", "description": "d", "severity": "low", "confidence": 0.4}
            ])
            self.assertEqual(out["success"], 1)

    def test_sentinel_retry_on_timeout_then_success(self):
        from community_ai_audit.connectors.sentinel_connector import SentinelConnector

        c = SentinelConnector()
        shared_key = base64.b64encode(b"secretkey").decode("utf-8")

        with patch("community_ai_audit.connectors.sentinel_connector.requests.post") as mock_post, \
             patch("community_ai_audit.connectors.sentinel_connector.requests.get") as mock_get:
            # Queue for POST calls: Timeout, Timeout, Success
            # First GET for validation returns 200
            mock_get.return_value = _FakeResp(200)
            mock_post.side_effect = [
                _FakeResp(500, raise_for_status=requests.exceptions.Timeout("timeout")),
                _FakeResp(500, raise_for_status=requests.exceptions.Timeout("timeout")),
                _FakeResp(200)
            ]
            
            c.connect({
                "workspace_id": "workspace123",
                "shared_key": shared_key,
                "log_type": "AIAudit",
                "retry": {"max_attempts": 3},
            })
            out = c.send_batch([{"title": "t", "description": "d", "severity": "low"}])
            self.assertEqual(out["success"], 1)
            self.assertEqual(mock_post.call_count, 3)

    def test_event_validation(self):
        from community_ai_audit.connectors.base import validate_event, validate_events

        # valid event
        ev1 = {"title": "test", "severity": "high", "confidence": 0.8}
        warns = validate_event(ev1)
        self.assertEqual(warns, [])

        # missing required
        ev2 = {"description": "no title"}
        warns = validate_event(ev2)
        self.assertTrue(any("missing required fields" in w for w in warns))

        # bad confidence type
        ev3 = {"title": "t", "severity": "medium", "confidence": "high"}
        warns = validate_event(ev3, strict=True)
        self.assertTrue(any("'confidence' should be numeric" in w for w in warns))

        # batch validation
        batch = [ev1, ev2, ev3]
        summary = validate_events(batch, strict=True)
        self.assertEqual(summary["valid"], 1)  # only ev1 valid
        self.assertEqual(summary["warnings"], 2)  # ev2 + ev3 warned

    def test_normalize_severity(self):
        from community_ai_audit.connectors.base import normalize_severity, severity_rank

        self.assertEqual(normalize_severity("CRITICAL"), "critical")
        self.assertEqual(normalize_severity("error"), "high")
        self.assertEqual(normalize_severity("WARNING"), "medium")
        self.assertEqual(normalize_severity("info"), "info")
        self.assertEqual(normalize_severity("unknown"), "unknown")
        self.assertEqual(normalize_severity(""), "unknown")

        self.assertGreaterEqual(severity_rank("critical"), severity_rank("high"))
        self.assertGreaterEqual(severity_rank("high"), severity_rank("medium"))
        self.assertGreaterEqual(severity_rank("medium"), severity_rank("low"))
        self.assertGreaterEqual(severity_rank("low"), severity_rank("info"))
        self.assertGreaterEqual(severity_rank("info"), severity_rank("unknown"))

    def test_chunk_list(self):
        from community_ai_audit.connectors.base import chunk_list

        data = [1, 2, 3, 4, 5]
        self.assertEqual(chunk_list(data, 2), [[1, 2], [3, 4], [5]])
        self.assertEqual(chunk_list(data, 10), [[1, 2, 3, 4, 5]])
        self.assertEqual(chunk_list([], 3), [])
        with self.assertRaises(ValueError):
            chunk_list(data, 0)

    def test_flatten_metadata(self):
        from community_ai_audit.connectors.base import flatten_metadata

        meta = {
            "simple": "value",
            "list": ["a", "b", "c"],
            "nested": {"inner": 42, "deep": {"x": "y"}},
        }
        flat = flatten_metadata(meta, prefix="m_")
        self.assertEqual(flat["m_simple"], "value")
        self.assertEqual(flat["m_list"], "a, b, c")
        self.assertEqual(flat["m_nested_inner"], "42")
        self.assertEqual(flat["m_nested_deep_x"], "y")


if __name__ == "__main__":
    unittest.main()