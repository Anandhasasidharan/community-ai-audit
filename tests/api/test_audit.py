"""Tests for audit job submission and status endpoints."""

import os

os.environ["DATABASE_URL"] = "sqlite://"

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from community_ai_audit.api.server import app
from community_ai_audit.api.deps import current_user


@pytest.fixture
def client():
    app.dependency_overrides[current_user] = lambda: {"role": "admin"}
    with TestClient(app) as c:
        yield c


def test_submit_audit(client):
    resp = client.post("/audit", json={"model": "gpt2", "provider": "huggingface"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert "job_id" in data


def test_get_audit_not_found(client):
    resp = client.get("/audit/nonexistent")
    assert resp.status_code == 404


def test_submit_and_get(client):
    resp = client.post("/audit", json={"model": "gpt2", "provider": "huggingface"})
    job_id = resp.json()["job_id"]
    resp = client.get(f"/audit/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["job_id"] == job_id
