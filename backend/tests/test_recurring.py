import json
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db.crud import get_cross_statement_recurring, save_statement
from app.db.database import get_session
from app.db.models import StatementDB
from app.main import app


def make_result(account_number: str) -> dict:
    return {
        "result": {
            "account_info": {
                "account_number": account_number,
                "bank_name": "Test Bank",
                "account_holder": "Test User",
                "statement_period": {"from": "2025-01-01", "to": "2025-01-31"},
            },
            "transactions": [],
            "confidence_summary": {
                "overall_score": 0.9,
                "total_transactions": 0,
                "high_confidence_txns": 0,
            },
        }
    }


NETFLIX_CANDIDATE = {
    "merchant": "NETFLIX",
    "count": 3,
    "avg_amount": 649.0,
    "std_amount": 0.0,
    "cv": 0.0,
    "first_seen": "2025-01-05",
    "last_seen": "2025-01-05",
    "common_days": [5],
}


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def mem_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _get_test_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _get_test_session
    yield app
    app.dependency_overrides.clear()


def test_cross_recurring_detected(session):
    """Merchant in recurring_candidates in 2 statements → confirmed list contains it."""
    save_statement(session, "hash1", "jan.csv", make_result("ACC001"), recurring_candidates=[NETFLIX_CANDIDATE])
    save_statement(session, "hash2", "feb.csv", make_result("ACC001"), recurring_candidates=[NETFLIX_CANDIDATE])

    confirmed = get_cross_statement_recurring("ACC001", session)

    assert len(confirmed) == 1
    assert confirmed[0]["merchant"] == "NETFLIX"
    assert confirmed[0]["statement_count"] == 2
    assert confirmed[0]["avg_amount"] == 649.0


def test_cross_recurring_single_statement(session):
    """Only 1 statement → empty confirmed list (need ≥2 to confirm)."""
    save_statement(session, "hash1", "jan.csv", make_result("ACC002"), recurring_candidates=[NETFLIX_CANDIDATE])

    confirmed = get_cross_statement_recurring("ACC002", session)

    assert confirmed == []


def test_cross_recurring_different_accounts(session):
    """2 statements with different account numbers → empty for either account queried separately."""
    save_statement(session, "hash1", "jan.csv", make_result("ACC003"), recurring_candidates=[NETFLIX_CANDIDATE])
    save_statement(session, "hash2", "feb.csv", make_result("ACC004"), recurring_candidates=[NETFLIX_CANDIDATE])

    assert get_cross_statement_recurring("ACC003", session) == []
    assert get_cross_statement_recurring("ACC004", session) == []


async def test_recurring_endpoint_returns_empty_not_404(mem_client):
    """Endpoint returns empty confirmed list (not 404) when no confirmed merchants exist."""
    async with AsyncClient(
        transport=ASGITransport(app=mem_client), base_url="http://test"
    ) as client:
        r = await client.get("/api/statements/recurring?account_number=UNKNOWN999")
    assert r.status_code == 200
    data = r.json()
    assert data["confirmed_recurring"] == []
    assert data["account_number"] == "UNKNOWN999"
