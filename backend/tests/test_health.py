import pytest


async def test_health_returns_200(client):
    response = await client.get("/api/health")
    assert response.status_code == 200


async def test_health_returns_correct_json(client):
    response = await client.get("/api/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
