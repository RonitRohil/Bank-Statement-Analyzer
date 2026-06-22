# Sprint-06 Prompt 04 — BSA-16: Category-Correction Learning Loop

## Task: Wire up the `CorrectionDB` table — POST corrections + re-parse override

**Context:** The `CorrectionDB` table was designed in ADR-002 and created in the initial Alembic migration (Sprint-04). The fingerprint format was documented in `crud.py` as CR-S4-03 (Sprint-05). This ticket wires it up: POST endpoint to store corrections, re-parse logic to apply them, and a frontend "Fix category" button.

**Files to read first:**

- `backend/app/db/models.py` — read `CorrectionDB` schema
- `backend/app/db/crud.py` — read the fingerprint comment (CR-S4-03) and `save_statement()`
- `backend/app/routers/analyze.py` — understand the analysis pipeline
- `backend/app/models/schemas.py`
- `backend/app/main.py`
- `backend/app/services/categories.py` — read `CANONICAL_CATEGORIES`
- `frontend/components/TransactionTable.tsx`
- `frontend/services/api.ts`
- `frontend/types.ts`

---

## Backend: Add correction CRUD to `crud.py`

Add two functions to `backend/app/db/crud.py`:

```python
import hashlib  # already imported

def fingerprint_transaction(transaction_date: str, amount: float, narration: str) -> str:
    """
    Compute the correction fingerprint for a transaction.
    Format: SHA-256 of "{transaction_date}:{amount}:{narration[:100]}"
    Normalize narration: strip whitespace, lowercase.
    This MUST match the client-side fingerprint computation.
    """
    norm_narration = (narration or "").strip().lower()[:100]
    raw = f"{transaction_date}:{amount}:{norm_narration}"
    return hashlib.sha256(raw.encode()).hexdigest()


def save_correction(
    session: Session,
    fingerprint: str,
    corrected_category: str,
    corrected_merchant: str | None = None,
) -> CorrectionDB:
    """Upsert a correction keyed by fingerprint."""
    from app.db.models import CorrectionDB
    existing = session.exec(
        select(CorrectionDB).where(CorrectionDB.fingerprint == fingerprint)
    ).first()
    if existing:
        existing.corrected_category = corrected_category
        if corrected_merchant is not None:
            existing.corrected_merchant = corrected_merchant
        session.add(existing)
    else:
        correction = CorrectionDB(
            fingerprint=fingerprint,
            corrected_category=corrected_category,
            corrected_merchant=corrected_merchant,
        )
        session.add(correction)
    session.commit()
    return existing or correction


def get_correction(session: Session, fingerprint: str):
    """Look up a stored correction by fingerprint. Returns None if not found."""
    from app.db.models import CorrectionDB
    return session.exec(
        select(CorrectionDB).where(CorrectionDB.fingerprint == fingerprint)
    ).first()
```

---

## Backend: `backend/app/routers/corrections.py` (new file)

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.db.crud import fingerprint_transaction, save_correction
from app.db.database import get_session
from app.services.categories import CANONICAL_CATEGORIES

router = APIRouter()

class CorrectionRequest(BaseModel):
    transaction_date: str
    amount: float
    narration: str
    corrected_category: str
    corrected_merchant: str | None = None

class CorrectionResponse(BaseModel):
    fingerprint: str
    corrected_category: str
    corrected_merchant: str | None

@router.post("/api/corrections", response_model=CorrectionResponse, status_code=201)
def submit_correction(req: CorrectionRequest, session: Session = Depends(get_session)):
    if req.corrected_category not in CANONICAL_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown category '{req.corrected_category}'. Valid values: {CANONICAL_CATEGORIES}"
        )
    fp = fingerprint_transaction(req.transaction_date, req.amount, req.narration)
    correction = save_correction(session, fp, req.corrected_category, req.corrected_merchant)
    return CorrectionResponse(
        fingerprint=fp,
        corrected_category=req.corrected_category,
        corrected_merchant=req.corrected_merchant,
    )
```

Register `corrections.router` in `backend/app/main.py`.

---

## Backend: Apply corrections during re-parse in `analyze.py`

After `enrich_with_llm()` and before building the final response, add a correction-override pass.

**In `backend/app/routers/analyze.py`**, after the enrichment block, add:

```python
# --- Correction override pass ---
# If a user has corrected a transaction's category before, apply the stored override.
from app.db.crud import fingerprint_transaction, get_correction

if db_session := ...:  # only run when the DB session is available (persist=true path)
    for txn in result["result"]["transactions"]:
        fp = fingerprint_transaction(
            txn.get("transaction_date", ""),
            txn.get("amount", 0.0),
            txn.get("narration", ""),
        )
        correction = get_correction(session, fp)
        if correction:
            txn["category"] = [correction.corrected_category]
            if correction.corrected_merchant:
                txn["merchant"] = correction.corrected_merchant
```

**Implementation notes:**

- Only run the correction pass when `persist=true` is set (i.e., when a DB session is active). The stateless path does not need corrections.
- The session variable is already available in the analyze router when `persist=true` — read the existing code carefully before adding this.
- Do not break the stateless (no persist) code path.

---

## Frontend: `frontend/components/TransactionTable.tsx` — add "Fix" button

In the existing transaction table, add a "✏ Fix" button per row in the Category column.

**Behavior:**

- Small link-style button next to the category name: "✏ Fix"
- On click: opens a small inline dropdown in that row. Options: all 16 categories from `CANONICAL_CATEGORIES` (hardcode the list or fetch from a new `GET /api/categories` endpoint — hardcode is simpler for now).
- On category select: call `POST /api/corrections` with the transaction's `transaction_date`, `amount`, `narration`, and the selected category.
- On success: show a "📌 Corrected" badge in the row, update the displayed category to the selected one.
- On error: show a small red error text "Failed to save — try again".

**Hardcoded category list for the dropdown** (from `CANONICAL_CATEGORIES`):

```
Food & Dining, Shopping, Utilities, Healthcare, Transportation, Entertainment,
Travel, Education, Salary & Income, Investment, Insurance, EMI & Loan,
Rent, Subscription, Transfer, Other
```

---

## Frontend: `frontend/services/api.ts`

Add:

```typescript
export async function submitCorrection(
  transactionDate: string,
  amount: number,
  narration: string,
  correctedCategory: string,
  correctedMerchant?: string,
) {
  const res = await fetch(`${API_BASE}/api/corrections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      transaction_date: transactionDate,
      amount,
      narration,
      corrected_category: correctedCategory,
      corrected_merchant: correctedMerchant ?? null,
    }),
  });
  if (!res.ok) throw new Error(`Correction failed: ${res.status}`);
  return res.json();
}
```

---

## Tests: `backend/tests/test_corrections.py` (new file)

Write ≥4 tests:

| Test                                            | What it checks                                                               |
| ----------------------------------------------- | ---------------------------------------------------------------------------- |
| `test_submit_correction_201`                    | POST valid correction → 201 → fingerprint in response                        |
| `test_correction_upserts`                       | POST same transaction twice with different categories → second category wins |
| `test_invalid_category_422`                     | POST unknown category → 422                                                  |
| `test_get_correction_returns_none_when_missing` | `get_correction()` on unknown fingerprint → returns None                     |

---

## Constraints

- Do not change `CorrectionDB` schema in `models.py` — it's already correct from Sprint-04.
- Do not add the correction pass to the stateless (no-persist) code path.
- The fingerprint normalization (strip + lowercase + `[:100]`) must be documented in `fingerprint_transaction()`. Any future change to this function MUST be backward-compatible or migrations will break.
- Match the existing style: no bare `except:`, explicit type hints, `logger.warning()` on skipped corrections.

## Verification

```bash
cd backend && pytest tests/test_corrections.py -v
pytest --tb=short -q  # full suite — no regressions
```

Manual: upload a statement with persist, fix a "Other" category transaction → refresh page → category shows the correction.

## Changelog entry required

Add to `docs/changelog.md`.
