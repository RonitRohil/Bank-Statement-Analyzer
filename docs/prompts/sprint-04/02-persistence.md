# Prompt 02 — BSA-19: Persistence Implementation (SQLite / SQLModel)

## Task: Implement the SQLite persistence layer

**Context:** The data model was designed and decided in Sprint-03 (ADR-002 — `docs/adr-002-persistence.md`). This prompt is implementation only. Do not relitigate SQLite vs. Postgres. Build exactly what the ADR specifies.

The stateless path (no `persist` flag) **must continue to work unchanged**. Storage is additive.

**Files to read first:**
- `docs/adr-002-persistence.md` — full table schema (mandatory read)
- `backend/app/models/schemas.py` — existing Pydantic models to reference
- `backend/app/routers/analyze.py` — where the persistence hook will be inserted
- `backend/app/config/settings.py` — where new settings go

---

## Step 1 — Add dependencies

**File:** `backend/requirements.txt`

Add:
```
sqlmodel==0.0.21
alembic==1.13.1
```

Do not change any existing dependency versions.

---

## Step 2 — Create DB table models

**File (new):** `backend/app/db/models.py`

Create three SQLModel table models that mirror the ADR schema. Keep them separate from the Pydantic response schemas in `schemas.py` — don't turn the existing `Transaction` schema into a table model.

```python
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class StatementDB(SQLModel, table=True):
    __tablename__ = "statements"
    id: Optional[int] = Field(default=None, primary_key=True)
    file_hash: str = Field(unique=True, index=True)      # SHA-256 of file bytes — dedup key
    original_filename: str
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    period_from: Optional[str] = None                    # ISO date
    period_to: Optional[str] = None                      # ISO date
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    confidence_overall: Optional[float] = None

class TransactionDB(SQLModel, table=True):
    __tablename__ = "transactions"
    id: Optional[int] = Field(default=None, primary_key=True)
    statement_id: int = Field(foreign_key="statements.id")
    transaction_date: Optional[str] = None
    amount: Optional[float] = None
    transaction_type: Optional[str] = None
    narration: Optional[str] = None
    balance: Optional[float] = None
    payment_method: Optional[str] = None
    merchant: Optional[str] = None
    category: Optional[str] = None      # JSON-encoded list: '["Food & Dining"]'
    payment_gateway: Optional[str] = None
    transaction_reference: Optional[str] = None
    confidence_score: Optional[float] = None
    llm_enriched: bool = False

class CorrectionDB(SQLModel, table=True):
    __tablename__ = "corrections"
    id: Optional[int] = Field(default=None, primary_key=True)
    fingerprint: str = Field(unique=True, index=True)    # SHA-256 of (date+amount+narration)
    corrected_category: str
    corrected_merchant: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

**Constraints:**
- `category` is stored as a JSON string (not a separate table). Use `json.dumps(txn.category)` on write, `json.loads(row.category)` on read.
- Do not add relationships or lazy-loading — keep it simple.
- Create `backend/app/db/__init__.py` as an empty package init.

---

## Step 3 — Database engine + session factory

**File (new):** `backend/app/db/database.py`

```python
import os
from sqlmodel import SQLModel, create_engine, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./statements.db")

# For SQLite: check_same_thread=False needed for FastAPI's thread pool
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def create_db_and_tables():
    """Called at startup to create all tables if they don't exist."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency — yields a SQLModel Session."""
    with Session(engine) as session:
        yield session
```

**Notes:**
- `DATABASE_URL` defaults to `sqlite:///./statements.db` (relative to where uvicorn is launched — same directory as `run.py`).
- For tests, override `DATABASE_URL=sqlite:///:memory:` in the test environment.
- `echo=False` in production; set `echo=True` only in debug mode.

---

## Step 4 — Add `DATABASE_URL` to settings

**File:** `backend/app/config/settings.py`

Add:
```python
database_url: str = "sqlite:///./statements.db"
```

Update `backend/app/db/database.py` to read `settings.database_url` instead of `os.getenv` directly.

---

## Step 5 — Call `create_db_and_tables` at startup

**File:** `backend/app/main.py`

In the `lifespan` async context manager (or at module level if lifespan doesn't exist yet), add:

```python
from app.db.database import create_db_and_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    logger.info("Database tables ready")
    yield
    logger.info("Shutting down")
```

If `lifespan` already exists, add the `create_db_and_tables()` call before the `yield`.

---

## Step 6 — Persistence helper functions

**File (new):** `backend/app/db/crud.py`

```python
import hashlib, json
from typing import Optional
from sqlmodel import Session, select
from app.db.models import StatementDB, TransactionDB


def hash_file(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def find_statement_by_hash(session: Session, file_hash: str) -> Optional[StatementDB]:
    return session.exec(select(StatementDB).where(StatementDB.file_hash == file_hash)).first()


def save_statement(session: Session, file_hash: str, filename: str, result: dict) -> StatementDB:
    account_info = result.get("result", {}).get("account_info", {})
    period = account_info.get("statement_period") or {}
    summary = result.get("result", {}).get("confidence_summary", {})

    stmt = StatementDB(
        file_hash=file_hash,
        original_filename=filename,
        account_number=account_info.get("account_number"),
        bank_name=account_info.get("bank_name"),
        account_holder=account_info.get("account_holder"),
        period_from=period.get("from"),
        period_to=period.get("to"),
        confidence_overall=summary.get("overall_score"),
    )
    session.add(stmt)
    session.flush()   # populate stmt.id without committing

    for txn in result.get("result", {}).get("transactions", []):
        row = TransactionDB(
            statement_id=stmt.id,
            transaction_date=txn.get("transaction_date"),
            amount=txn.get("amount"),
            transaction_type=txn.get("transaction_type"),
            narration=txn.get("narration"),
            balance=txn.get("balance"),
            payment_method=txn.get("payment_method"),
            merchant=txn.get("merchant"),
            category=json.dumps(txn.get("category") or []),
            payment_gateway=txn.get("payment_gateway"),
            transaction_reference=txn.get("transaction_reference"),
            confidence_score=txn.get("confidence_score"),
            llm_enriched=txn.get("llm_enriched", False),
        )
        session.add(row)

    session.commit()
    session.refresh(stmt)
    return stmt
```

---

## Step 7 — Wire dedup check into the analyze endpoint

**File:** `backend/app/routers/analyze.py`

Add an optional query parameter `persist: bool = False`. When `True`:

1. Read the uploaded file bytes and compute `file_hash = hash_file(file_bytes)`.
2. Call `find_statement_by_hash(session, file_hash)`.
3. If found → return a 200 with the stored result (or a simple `{"cached": True, "statement_id": stmt.id}` — see note below).
4. If not found → parse as normal, then call `save_statement(session, file_hash, filename, result)`.

**Important constraint:** The dedup check runs only when `persist=True`. The default `persist=False` path must be byte-for-byte identical to today's behavior — no DB reads, no DB writes, no added latency.

**Note on cached response shape:** For now, returning `{"cached": True, "statement_id": stmt.id, "message": "Statement already analyzed"}` is acceptable. Full re-hydration of the stored result from DB is a BSA-17 concern (when history features need to retrieve past results).

**File bytes caveat:** `UploadFile` is consumed (streamed) when saving to disk. Read the bytes before saving, then write them yourself. Or seek back after reading: `await file.seek(0)` if the file object supports it.

---

## Step 8 — Initialize Alembic

Run in `backend/`:

```bash
alembic init alembic
```

Edit `alembic/env.py` to import `SQLModel.metadata`:

```python
from app.db.models import StatementDB, TransactionDB, CorrectionDB  # noqa — registers tables
from sqlmodel import SQLModel
target_metadata = SQLModel.metadata
```

Generate the first migration:

```bash
alembic revision --autogenerate -m "initial schema: statements, transactions, corrections"
```

Review the generated migration file in `alembic/versions/` — it should create all three tables.

Apply:

```bash
alembic upgrade head
```

Commit `alembic/` to git.

---

## Step 9 — Add a `GET /api/statements` endpoint

**File (new):** `backend/app/routers/statements.py`

Simple list endpoint — no pagination yet:

```python
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.db.database import get_session
from app.db.models import StatementDB

router = APIRouter()

@router.get("/api/statements")
def list_statements(session: Session = Depends(get_session)):
    statements = session.exec(select(StatementDB).order_by(StatementDB.uploaded_at.desc())).all()
    return {"statements": [s.model_dump() for s in statements]}
```

Register in `backend/app/main.py`:

```python
from app.routers import statements
app.include_router(statements.router)
```

---

## Step 10 — Tests

**File (new):** `backend/tests/test_persistence.py`

Write tests using an in-memory SQLite DB:

```python
import pytest
from sqlmodel import create_engine, Session, SQLModel
from app.db.models import StatementDB, TransactionDB
from app.db.crud import find_statement_by_hash, save_statement

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
```

Test cases:
1. `save_statement` creates a `StatementDB` row with the correct `file_hash`.
2. `find_statement_by_hash` returns the row after saving.
3. Saving the same hash twice raises an `IntegrityError` (or a handled duplicate).
4. Uploading a statement with `persist=True` via the HTTP client → response 200 + `statement_id` in DB.
5. Uploading the same file again → response contains `cached: True`.

---

## Documentation

1. `docs/changelog.md` — add entry for BSA-19.
2. `docs/tech-debt.md` — mark BSA-19 as done. Open any new debt items you discover.
3. `CLAUDE.md` — update the "Deployment Notes" section: add "SQLite DB at `statements.db`; back it up with `cp statements.db statements.db.bak`."
4. `backend/.env.example` — add `DATABASE_URL=sqlite:///./statements.db`.

**Encryption decision (document in CLAUDE.md):** For this sprint, no encryption at rest. The `.db` file contains real financial data. Users are responsible for OS-level disk encryption and backup. This decision must be revisited before any networked or multi-user deployment. Log this as `docs/adr-002-persistence.md` footnote.

**Verification:**

```bash
cd backend
pytest tests/test_persistence.py -v
pytest -v     # all tests must still pass
```

Upload two statements via Swagger UI with `?persist=true`. `GET /api/statements` should list both. Upload one of them again — response should contain `cached: True`.
