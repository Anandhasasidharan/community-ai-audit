"""Tests for usage metering endpoint."""
import os
os.environ["DATABASE_URL"] = "sqlite://"

from fastapi.testclient import TestClient
import pytest
from community_ai_audit.api.server import app
from community_ai_audit.api.deps import current_user


@pytest.fixture
def client():
    app.dependency_overrides[current_user] = lambda: {"user_id": "test_user", "role": "user"}
    with TestClient(app) as c:
        yield c


def test_usage_records_on_audit(client):
    client.post("/audit", json={"model": "gpt2", "provider": "huggingface"})
    resp = client.get("/usage")
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) >= 1
    assert records[0]["endpoint"] == "/audit"
    assert records[0]["method"] == "POST"


def test_usage_empty(client):
    resp = client.get("/usage")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
