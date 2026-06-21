import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def sample_transactions_payload():
    return [
        {
            "transaction_date": "2025-01-15",
            "transaction_type": "DEBIT",
            "amount": 1500.00,
            "balance": 48500.00,
            "narration": "UPI/123456/Swiggy/HDFC",
            "payment_method": "UPI",
            "merchant": "SWIGGY",
            "category": ["FOOD_DELIVERY"],
            "upi_id": "swiggy@hdfc",
            "transaction_reference": "RRN123456",
            "bank_peer": "HDFC",
            "payment_gateway": None,
            "confidence_score": 0.92,
            "llm_enriched": False,
            "remarks": [],
        },
        {
            "transaction_date": "2025-01-20",
            "transaction_type": "CREDIT",
            "amount": 50000.00,
            "balance": 98500.00,
            "narration": "NEFT/SALARY/EMPLOYER",
            "payment_method": "NEFT",
            "merchant": None,
            "category": ["SALARY"],
            "upi_id": None,
            "transaction_reference": "UTR789012",
            "bank_peer": None,
            "payment_gateway": None,
            "confidence_score": 0.95,
            "llm_enriched": False,
            "remarks": ["SALARY"],
        },
        {
            "transaction_date": "2025-01-22",
            "transaction_type": "DEBIT",
            "amount": 999.00,
            "balance": 97501.00,
            "narration": "AMAZON/ORDER/12345",
            "payment_method": "CARD",
            "merchant": "AMAZON",
            "category": ["E-COMMERCE", "SHOPPING"],
            "upi_id": None,
            "transaction_reference": "TXN345678",
            "bank_peer": None,
            "payment_gateway": None,
            "confidence_score": 0.88,
            "llm_enriched": True,
            "remarks": [],
        },
    ]
