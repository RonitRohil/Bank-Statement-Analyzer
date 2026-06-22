import pytest
from pathlib import Path

from httpx import AsyncClient, ASGITransport
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db.crud import find_statement_by_hash, save_statement
from app.db.database import get_session
from app.db.models import StatementDB, TransactionDB
from app.main import app

FIXTURES_DIR = Path(__file__).parent / "fixtures"

SAMPLE_RESULT = {
    "result": {
        "account_info": {
            "account_number": "123456",
            "bank_name": "Test Bank",
            "account_holder": "Test User",
            "statement_period": {"from": "2025-01-01", "to": "2025-01-31"},
        },
        "transactions": [
            {
                "transaction_date": "2025-01-10",
                "amount": 1000.0,
                "transaction_type": "CREDIT",
                "narration": "Salary",
                "balance": 10000.0,
                "payment_method": "NEFT",
                "merchant": None,
                "category": ["SALARY"],
                "payment_gateway": None,
                "transaction_reference": "REF123",
                "confidence_score": 0.9,
                "llm_enriched": False,
            }
        ],
        "confidence_summary": {
            "overall_score": 0.9,
            "total_transactions": 1,
            "high_confidence_txns": 1,
        },
    }
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
    """HTTP test client backed by an isolated in-memory SQLite — never touches the real DB."""
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


# --- Unit tests (in-memory session) ---


def test_save_statement_creates_row_with_correct_hash(session):
    stmt = save_statement(session, "abc123hash", "test.csv", SAMPLE_RESULT)
    assert stmt.id is not None
    assert stmt.file_hash == "abc123hash"
    assert stmt.original_filename == "test.csv"


def test_find_statement_by_hash_returns_saved_row(session):
    save_statement(session, "findme456", "test2.csv", SAMPLE_RESULT)
    found = find_statement_by_hash(session, "findme456")
    assert found is not None
    assert found.file_hash == "findme456"


def test_find_statement_by_hash_returns_none_for_unknown(session):
    assert find_statement_by_hash(session, "doesnotexist") is None


def test_duplicate_hash_raises_integrity_error(session):
    save_statement(session, "dup123", "test.csv", SAMPLE_RESULT)
    with pytest.raises(IntegrityError):
        save_statement(session, "dup123", "test_dup.csv", SAMPLE_RESULT)


# --- HTTP integration tests ---


async def test_persist_true_saves_statement_returns_statement_id(mem_client):
    csv_path = FIXTURES_DIR / "sample.csv"
    async with AsyncClient(
        transport=ASGITransport(app=mem_client), base_url="http://test"
    ) as client:
        with open(csv_path, "rb") as f:
            response = await client.post(
                "/api/analyze/bank/statement?persist=true",
                files={"file": ("sample.csv", f, "text/csv")},
            )
    assert response.status_code == 200
    data = response.json()
    assert data.get("success") == 1
    # statement_id is not in the normal response — but no "cached" key either
    assert "cached" not in data


async def test_persist_true_second_upload_returns_cached(mem_client):
    csv_path = FIXTURES_DIR / "sample.csv"
    file_content = csv_path.read_bytes()

    async with AsyncClient(
        transport=ASGITransport(app=mem_client), base_url="http://test"
    ) as client:
        # First upload — parsed and stored
        r1 = await client.post(
            "/api/analyze/bank/statement?persist=true",
            files={"file": ("sample.csv", file_content, "text/csv")},
        )
        assert r1.status_code == 200
        assert r1.json().get("cached") is None  # not cached on first upload

        # Second upload — same bytes → dedup hit
        r2 = await client.post(
            "/api/analyze/bank/statement?persist=true",
            files={"file": ("sample.csv", file_content, "text/csv")},
        )
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2.get("cached") is True
    assert "statement_id" in data2


async def test_get_statement_transactions_returns_list(mem_client):
    csv_path = FIXTURES_DIR / "sample.csv"
    async with AsyncClient(
        transport=ASGITransport(app=mem_client), base_url="http://test"
    ) as client:
        r_upload = await client.post(
            "/api/analyze/bank/statement?persist=true",
            files={"file": ("sample.csv", csv_path.read_bytes(), "text/csv")},
        )
        assert r_upload.status_code == 200

        # Resolve the statement_id from the listing — analyze does not echo it on first upload
        r_list = await client.get("/api/statements?limit=1&offset=0")
        assert r_list.status_code == 200
        statement_id = r_list.json()["statements"][0]["id"]

        r_txns = await client.get(f"/api/statements/{statement_id}/transactions")
    assert r_txns.status_code == 200
    data = r_txns.json()
    assert "transactions" in data
    assert isinstance(data["transactions"], list)
    assert len(data["transactions"]) > 0


async def test_get_statement_transactions_404(mem_client):
    async with AsyncClient(
        transport=ASGITransport(app=mem_client), base_url="http://test"
    ) as client:
        r = await client.get("/api/statements/999/transactions")
    assert r.status_code == 404


async def test_list_statements_pagination(mem_client):
    csv_path = FIXTURES_DIR / "sample.csv"
    file_content = csv_path.read_bytes()

    # Use two distinct file contents to bypass the SHA-256 dedup guard
    content_a = file_content + b"\n# statement-a"
    content_b = file_content + b"\n# statement-b"

    async with AsyncClient(
        transport=ASGITransport(app=mem_client), base_url="http://test"
    ) as client:
        await client.post(
            "/api/analyze/bank/statement?persist=true",
            files={"file": ("a.csv", content_a, "text/csv")},
        )
        await client.post(
            "/api/analyze/bank/statement?persist=true",
            files={"file": ("b.csv", content_b, "text/csv")},
        )

        r1 = await client.get("/api/statements?limit=1&offset=0")
        assert r1.status_code == 200
        d1 = r1.json()
        assert len(d1["statements"]) == 1

        r2 = await client.get("/api/statements?limit=1&offset=1")
        assert r2.status_code == 200
        d2 = r2.json()
        assert len(d2["statements"]) == 1

        # The two pages must be different records
        assert d1["statements"][0]["id"] != d2["statements"][0]["id"]
