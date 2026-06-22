import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db.crud import save_statement
from app.db.database import get_session
from app.main import app


def _result(account_number: str, month: str, debit_amount: float = 500.0):
    """Build a minimal save_statement-compatible result dict for a given month."""
    return {
        "result": {
            "account_info": {
                "account_number": account_number,
                "bank_name": "Test Bank",
                "account_holder": "Test User",
                "statement_period": {"from": f"{month}-01", "to": f"{month}-28"},
            },
            "transactions": [
                {
                    "transaction_date": f"{month}-15",
                    "amount": debit_amount,
                    "transaction_type": "DEBIT",
                    "narration": "UPI/123/Amazon",
                    "balance": 10000.0,
                    "payment_method": "UPI",
                    "merchant": "AMAZON",
                    "category": ["E-COMMERCE"],
                    "payment_gateway": None,
                    "transaction_reference": "REF001",
                    "confidence_score": 0.9,
                    "llm_enriched": False,
                },
                {
                    "transaction_date": f"{month}-20",
                    "amount": 5000.0,
                    "transaction_type": "CREDIT",
                    "narration": "NEFT/SALARY",
                    "balance": 15000.0,
                    "payment_method": "NEFT",
                    "merchant": None,
                    "category": ["SALARY"],
                    "payment_gateway": None,
                    "transaction_reference": "REF002",
                    "confidence_score": 0.95,
                    "llm_enriched": False,
                },
            ],
            "confidence_summary": {
                "overall_score": 0.9,
                "total_transactions": 2,
                "high_confidence_txns": 2,
            },
        }
    }


@pytest.fixture
def comparison_env():
    """Yields a Session that shares an in-memory engine with the HTTP client override.

    StaticPool forces a single connection so the fixture session and HTTP-override
    sessions all see the same in-memory SQLite database.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override

    with Session(engine) as session:
        yield session

    app.dependency_overrides.clear()


class TestMomComparison:
    async def test_compare_single_month(self, comparison_env):
        session = comparison_env
        save_statement(session, "hash-s1-001", "jan.csv", _result("ACC001", "2025-01"))

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get("/api/statements/compare?account_number=ACC001")

        assert r.status_code == 200
        data = r.json()
        assert data["account_number"] == "ACC001"
        assert data["total_months"] == 1
        assert len(data["months"]) == 1
        assert data["months"][0]["delta_expenses_pct"] is None

    async def test_compare_two_months(self, comparison_env):
        session = comparison_env
        save_statement(
            session, "hash-t2-001", "jan.csv", _result("ACC002", "2025-01", debit_amount=500.0)
        )
        save_statement(
            session, "hash-t2-002", "feb.csv", _result("ACC002", "2025-02", debit_amount=1000.0)
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get("/api/statements/compare?account_number=ACC002")

        assert r.status_code == 200
        data = r.json()
        assert data["total_months"] == 2
        months = data["months"]
        assert months[0]["delta_expenses_pct"] is None  # first month has no delta
        assert months[1]["delta_expenses_pct"] is not None  # second has a delta
        # Feb debit is double Jan debit → +100%
        assert months[1]["delta_expenses_pct"] == pytest.approx(100.0)

    async def test_compare_404_unknown_account(self, comparison_env):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get("/api/statements/compare?account_number=NOTEXIST")

        assert r.status_code == 404

    async def test_compare_no_account_param(self, comparison_env):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get("/api/statements/compare")

        assert r.status_code == 422
