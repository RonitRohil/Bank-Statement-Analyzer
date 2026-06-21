# Sprint-05 Prompt 01 — Housekeeping (CR-S4-01/02/03/05)

**Tickets:** CR-S4-01, CR-S4-02, CR-S4-03, CR-S4-05  
**Estimated time:** 45 minutes  
**Context:** `docs/code-review.md` (Sprint-04 review), `docs/sprint-05-plan.md`

This is the first commit of Sprint-05. Four small fixes from the Sprint-04 code review. Do them all in one commit.

---

## Files to Read First

- `backend/app/routers/statements.py` — current GET /api/statements handler
- `backend/app/routers/export.py` — export endpoint (filename sanitization)
- `backend/app/db/crud.py` — existing CRUD helpers (add fingerprint comment)
- `backend/app/db/models.py` — TransactionDB (for the new endpoint)
- `backend/app/models/schemas.py` — for response type on the new endpoint

---

## Changes to Make

### 1. CR-S4-02 — Add `GET /api/statements/{statement_id}/transactions`

**File:** `backend/app/routers/statements.py`

Add after the existing `list_statements` handler:

```python
from sqlmodel import select
from fastapi import HTTPException
from app.db.models import TransactionDB

@router.get("/api/statements/{statement_id}/transactions")
def get_statement_transactions(
    statement_id: int,
    session: Session = Depends(get_session),
):
    """Return all stored transactions for a specific statement."""
    txns = session.exec(
        select(TransactionDB).where(TransactionDB.statement_id == statement_id)
    ).all()
    if not txns:
        raise HTTPException(
            status_code=404,
            detail=f"No transactions found for statement {statement_id}",
        )
    return {"statement_id": statement_id, "transactions": [t.model_dump() for t in txns]}
```

Also add `limit: int = Query(default=100, le=500)` and `offset: int = Query(default=0)` parameters so large statements are paginated.

### 2. CR-S4-01 — Paginate `GET /api/statements`

**File:** `backend/app/routers/statements.py`

Modify the existing `list_statements` handler to accept `limit` and `offset`:

```python
from fastapi import Query

@router.get("/api/statements")
def list_statements(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
    session: Session = Depends(get_session),
):
    statements = session.exec(
        select(StatementDB)
        .order_by(StatementDB.uploaded_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {"statements": [s.model_dump() for s in statements], "limit": limit, "offset": offset}
```

### 3. CR-S4-05 — Sanitize `filename` in export endpoint

**File:** `backend/app/routers/export.py`

At the start of the `export_transactions` handler, add:

```python
import re
safe_name = re.sub(r"[^\w\-.]", "_", req.filename)
```

Then use `safe_name` in both `Content-Disposition` headers instead of `req.filename`.

### 4. CR-S4-03 — Document `CorrectionDB` fingerprint in crud.py

**File:** `backend/app/db/crud.py`

Add a comment block near the top of the file (after imports):

```python
# --- CorrectionDB fingerprint spec (for BSA-16 learning loop) ---
# fingerprint = SHA-256 of f"{transaction_date}:{amount}:{narration[:100]}"
# This must match the key used in save_correction() when BSA-16 is implemented.
# See: docs/sprint-05-plan.md → BSA-16 in P2 backlog
```

---

## Tests to Add

**File:** `backend/tests/test_persistence.py` (add to existing file)

Add 3 new tests:

1. `test_get_statement_transactions_returns_list` — persist a statement with `persist=true`, then `GET /api/statements/1/transactions` → 200 with `transactions` list
2. `test_get_statement_transactions_404` — `GET /api/statements/999/transactions` → 404
3. `test_list_statements_pagination` — upload 2 statements, `GET /api/statements?limit=1&offset=0` → 1 result; `?limit=1&offset=1` → 1 result

---

## Constraints

- Do NOT modify the Alembic migration — no schema changes in this prompt.
- Do NOT change any existing test assertions — these are additive changes only.
- Match the existing import style in `statements.py` (SQLModel `Session`, `select`, `Depends`).

---

## Verification

```bash
cd backend
pytest tests/test_persistence.py -v   # all tests including 3 new ones pass
pytest -v                              # full suite green (~41 tests)
```

Also confirm in Swagger UI (`http://localhost:8000/docs`) that:
- `GET /api/statements` now shows `limit` and `offset` query params
- `GET /api/statements/{statement_id}/transactions` appears in the docs
