import pytest


FIXTURE_TRANSACTIONS = [
    {
        "transaction_date": "2025-01-05",
        "transaction_type": "CREDIT",
        "amount": 50000.0,
        "merchant": None,
        "category": [],
        "narration": "SALARY",
    },
    {
        "transaction_date": "2025-01-10",
        "transaction_type": "DEBIT",
        "amount": 1200.0,
        "merchant": "AMAZON",
        "category": ["E-COMMERCE"],
        "narration": "Amazon order",
    },
    {
        "transaction_date": "2025-01-15",
        "transaction_type": "DEBIT",
        "amount": 800.0,
        "merchant": "SWIGGY",
        "category": ["FOOD_DELIVERY"],
        "narration": "Swiggy order",
    },
    {
        "transaction_date": "2025-01-20",
        "transaction_type": "DEBIT",
        "amount": 2000.0,
        "merchant": "AMAZON",
        "category": ["E-COMMERCE"],
        "narration": "Amazon electronics",
    },
    {
        "transaction_date": "2025-01-25",
        "transaction_type": "DEBIT",
        "amount": 500.0,
        "merchant": None,
        "category": ["UTILITY_BILL"],
        "narration": "Electricity bill",
    },
]


async def test_summary_math_fixture(client):
    response = await client.post(
        "/api/analyze/bank/summary",
        json={"transactions": FIXTURE_TRANSACTIONS},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["total_income"] == pytest.approx(50000.0)
    assert data["total_expenses"] == pytest.approx(4500.0)
    assert data["net"] == pytest.approx(45500.0)
    assert data["transaction_count"] == 5
    assert data["avg_transaction_amount"] == pytest.approx((50000 + 1200 + 800 + 2000 + 500) / 5, rel=1e-3)

    # AMAZON is the top merchant (total 3200), SWIGGY second (800)
    merchants = data["top_merchants"]
    assert merchants[0]["merchant"] == "AMAZON"
    assert merchants[0]["total"] == pytest.approx(3200.0)
    assert merchants[1]["merchant"] == "SWIGGY"

    # date_range should span Jan 5 to Jan 25
    assert data["date_range"]["from"] == "2025-01-05"
    assert data["date_range"]["to"] == "2025-01-25"


async def test_summary_empty_transactions(client):
    response = await client.post(
        "/api/analyze/bank/summary",
        json={"transactions": []},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["total_income"] == 0.0
    assert data["total_expenses"] == 0.0
    assert data["net"] == 0.0
    assert data["by_category"] == []
    assert data["top_merchants"] == []
    assert data["transaction_count"] == 0
    assert data["avg_transaction_amount"] == 0.0
    assert data["date_range"] is None


async def test_summary_bad_amount_returns_422(client):
    response = await client.post(
        "/api/analyze/bank/summary",
        json={"transactions": [{"amount": "oops", "transaction_type": "DEBIT"}]},
    )
    assert response.status_code == 422
