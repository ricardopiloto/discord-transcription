"""Unit tests for GET /health."""

from __future__ import annotations


def test_health_ok_when_ready(ready_client):
    response = ready_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["model"] == "small"
    assert data["compute_type"] == "int8"


def test_health_loading_returns_503(loading_client):
    response = loading_client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "loading"
    assert data["model"] == "small"
