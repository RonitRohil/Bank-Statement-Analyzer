import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db.crud import fingerprint_transaction, get_correction, save_correction
from app.db.database import get_session
from app.main import app


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


async def test_submit_correction_201(mem_client):
    async with AsyncClient(
        transport=ASGITransport(app=mem_client), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/corrections",
            json={
                "transaction_date": "2025-01-10",
                "amount": 1500.0,
                "narration": "UPI/123456/Swiggy/HDFC",
                "corrected_category": "Food & Dining",
            },
        )
    assert response.status_code == 201
    data = response.json()
    assert data["corrected_category"] == "Food & Dining"
    assert len(data["fingerprint"]) == 64  # SHA-256 hex digest


async def test_correction_upserts(mem_client):
    payload = {
        "transaction_date": "2025-01-10",
        "amount": 999.0,
        "narration": "AMAZON/ORDER/12345",
        "corrected_category": "Shopping",
    }
    async with AsyncClient(
        transport=ASGITransport(app=mem_client), base_url="http://test"
    ) as client:
        r1 = await client.post("/api/corrections", json=payload)
        assert r1.status_code == 201
        assert r1.json()["corrected_category"] == "Shopping"

        r2 = await client.post(
            "/api/corrections",
            json={**payload, "corrected_category": "Entertainment"},
        )
        assert r2.status_code == 201
        # Same fingerprint; second category wins
        assert r2.json()["corrected_category"] == "Entertainment"
        assert r1.json()["fingerprint"] == r2.json()["fingerprint"]


async def test_invalid_category_422(mem_client):
    async with AsyncClient(
        transport=ASGITransport(app=mem_client), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/corrections",
            json={
                "transaction_date": "2025-01-10",
                "amount": 500.0,
                "narration": "Some narration",
                "corrected_category": "InvalidCategory",
            },
        )
    assert response.status_code == 422
    assert "Unknown category" in response.json()["detail"]


def test_get_correction_returns_none_when_missing(session):
    result = get_correction(session, "nonexistentfingerprint1234567890abcdef")
    assert result is None


def test_fingerprint_transaction_is_deterministic():
    fp1 = fingerprint_transaction("2025-01-10", 1500.0, "  UPI/123  ")
    fp2 = fingerprint_transaction("2025-01-10", 1500.0, "  UPI/123  ")
    assert fp1 == fp2
    assert len(fp1) == 64


def test_save_correction_upserts_in_session(session):
    fp = fingerprint_transaction("2025-02-01", 200.0, "Netflix subscription")
    save_correction(session, fp, "Entertainment")
    c1 = get_correction(session, fp)
    assert c1 is not None
    assert c1.corrected_category == "Entertainment"

    save_correction(session, fp, "Refund")
    c2 = get_correction(session, fp)
    assert c2.corrected_category == "Refund"
