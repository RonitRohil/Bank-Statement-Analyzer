import pytest


async def test_export_csv(client, sample_transactions_payload):
    response = await client.post(
        "/api/export/transactions",
        json={
            "transactions": sample_transactions_payload,
            "format": "csv",
            "filename": "test",
        },
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "Date,Type,Amount" in response.text


async def test_export_xlsx(client, sample_transactions_payload):
    response = await client.post(
        "/api/export/transactions",
        json={
            "transactions": sample_transactions_payload,
            "format": "xlsx",
            "filename": "test",
        },
    )
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    assert len(response.content) > 0


async def test_export_empty_returns_400(client):
    response = await client.post(
        "/api/export/transactions", json={"transactions": [], "format": "csv"}
    )
    assert response.status_code == 400
