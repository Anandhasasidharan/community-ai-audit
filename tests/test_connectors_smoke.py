"""Connector smoke tests with mocked network/client dependencies.

These tests avoid real network calls and validate connector behavior at a
contract level (connect + send path).
"""

import base64
import sys
import types
import unittest
from unittest.mock import patch


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self):
        self.headers = {}
        self.last_post = None

    def get(self, *args, **kwargs):
        return _FakeResp(status_code=200)

    def post(self, *args, **kwargs):
        self.last_post = (args, kwargs)
        return _FakeResp(status_code=200, payload={"acknowledged": 1})


class _FakeRequests:
    Session = _FakeSession

    @staticmethod
    def get(*args, **kwargs):
        return _FakeResp(status_code=200)

    @staticmethod
    def post(*args, **kwargs):
        return _FakeResp(status_code=200, payload={"data": []})


class TestConnectorsSmoke(unittest.TestCase):
    def test_splunk_connect_and_send_batch(self):
        from community_ai_audit.connectors.splunk_connector import SplunkConnector

        c = SplunkConnector()
        with patch("community_ai_audit.connectors.splunk_connector.safe_import", return_value=_FakeRequests):
            c.connect({"hec_url": "https://splunk.local:8088", "hec_token": "tok"})
            out = c.send_batch([
                {"title": "t", "description": "d", "severity": "high", "confidence": 0.8}
            ])
            self.assertEqual(out["success"], 1)

    def test_datadog_connect_and_send_batch(self):
        from community_ai_audit.connectors.datadog_connector import DatadogConnector

        c = DatadogConnector()
        with patch("community_ai_audit.connectors.datadog_connector.safe_import", return_value=_FakeRequests):
            c.connect({"dd_api_key": "k", "dd_site": "datadoghq.com", "service": "ai-audit"})

        fake_requests_mod = types.SimpleNamespace(
            post=lambda *a, **k: _FakeResp(status_code=200),
            get=lambda *a, **k: _FakeResp(status_code=200),
        )
        with patch.dict(sys.modules, {"requests": fake_requests_mod}):
            out = c.send_batch([
                {"title": "t", "description": "d", "severity": "medium", "confidence": 0.6}
            ])
            self.assertEqual(out["success"], 1)

    def test_sentinel_connect_and_send_batch(self):
        from community_ai_audit.connectors.sentinel_connector import SentinelConnector

        c = SentinelConnector()
        shared_key = base64.b64encode(b"secretkey").decode("utf-8")

        with patch("community_ai_audit.connectors.sentinel_connector.safe_import", return_value=_FakeRequests):
            c.connect({
                "workspace_id": "workspace123",
                "shared_key": shared_key,
                "log_type": "AIAudit",
            })

        fake_requests_mod = types.SimpleNamespace(
            post=lambda *a, **k: _FakeResp(status_code=200),
        )
        with patch.dict(sys.modules, {"requests": fake_requests_mod}):
            out = c.send_batch([
                {"title": "t", "description": "d", "severity": "low", "confidence": 0.4}
            ])
            self.assertEqual(out["success"], 1)

    def test_elastic_send_batch_with_mock_client(self):
        from community_ai_audit.connectors.elastic_connector import ElasticConnector

        c = ElasticConnector()
        c._client = types.SimpleNamespace(
            bulk=lambda **kwargs: {
                "errors": False,
                "items": [{"index": {}}, {"index": {}}],
            }
        )
        c._index = "security-ai-audit"

        out = c.send_batch([
            {"title": "a", "description": "d", "severity": "high", "confidence": 0.9},
            {"title": "b", "description": "d", "severity": "low", "confidence": 0.2},
        ])
        self.assertEqual(out["success"], 2)
        self.assertEqual(out["failed"], 0)


if __name__ == "__main__":
    unittest.main()
