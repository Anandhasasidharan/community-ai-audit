"""Tests for health check endpoints."""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from community_ai_audit.api.server import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_ready():
    resp = client.get("/health/ready")
    assert resp.status_code == 200
