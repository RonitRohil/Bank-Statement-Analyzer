import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


async def test_analyze_csv_returns_200(client):
    csv_path = FIXTURES_DIR / "sample.csv"
    with open(csv_path, "rb") as f:
        response = await client.post(
            "/api/analyze/bank/statement",
            files={"file": ("sample.csv", f, "text/csv")},
        )
    assert response.status_code == 200


async def test_analyze_csv_response_shape(client):
    csv_path = FIXTURES_DIR / "sample.csv"
    with open(csv_path, "rb") as f:
        response = await client.post(
            "/api/analyze/bank/statement",
            files={"file": ("sample.csv", f, "text/csv")},
        )
    data = response.json()
    assert "success" in data
    assert "status_code" in data
    assert "message" in data
    assert "result" in data
    result = data["result"]
    assert "transactions" in result
    assert "account_info" in result
    assert "confidence_summary" in result
    assert isinstance(result["transactions"], list)


async def test_analyze_rejects_bad_extension(client):
    response = await client.post(
        "/api/analyze/bank/statement",
        files={"file": ("malware.exe", b"fake content", "application/octet-stream")},
    )
    assert response.status_code == 400


async def test_analyze_rejects_oversized_file(client):
    oversized_content = b"x" * (21 * 1024 * 1024)
    response = await client.post(
        "/api/analyze/bank/statement",
        files={"file": ("big.csv", oversized_content, "text/csv")},
    )
    assert response.status_code == 413


async def test_analyze_transactions_have_required_fields(client):
    csv_path = FIXTURES_DIR / "sample.csv"
    with open(csv_path, "rb") as f:
        response = await client.post(
            "/api/analyze/bank/statement",
            files={"file": ("sample.csv", f, "text/csv")},
        )
    transactions = response.json()["result"]["transactions"]
    assert len(transactions) > 0
    for txn in transactions:
        assert "transaction_date" in txn
        assert "narration" in txn
        assert "amount" in txn
        assert "transaction_type" in txn
        assert "confidence_score" in txn
