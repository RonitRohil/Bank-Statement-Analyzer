# Sprint-05 Prompt 03 — Cross-Statement Recurring Detection (BSA-07-full)

**Ticket:** BSA-07-full  
**Estimated time:** 2–3h  
**Priority:** P1 (do if prompt 02 is complete and capacity remains)  
**Context:** `docs/sprint-05-plan.md`, `docs/study/sprint-04-learnings.md` (BSA-07 lite section)

BSA-07 lite (Sprint-04) detects recurring merchants within a single statement. BSA-07-full confirms subscriptions across multiple statements — a Netflix charge appearing in Jan, Feb, and March is a high-confidence subscription, not a coincidence.

---

## Files to Read First

- `backend/app/services/insights.py` — `detect_recurring()` (the single-statement version)
- `backend/app/db/models.py` — StatementDB, TransactionDB
- `backend/app/db/crud.py` — existing CRUD helpers
- `backend/app/routers/statements.py` — existing statements router
- `backend/app/models/schemas.py` — add new response model here
- `frontend/components/MerchantInsights.tsx` — existing recurring pill (extend or complement)

---

## Design

### Storage strategy
Add `recurring_candidates_json: Optional[str] = None` to `StatementDB` and `save_statement()` in `crud.py`. When `persist=true`, after `detect_recurring()` runs in the analyze router, store the result as JSON alongside the statement. This avoids re-querying all transactions when the compare endpoint needs recurring data.

This requires a **new Alembic migration** — see below.

### Cross-statement logic
A merchant is "confirmed recurring" if it appears in `recurring_candidates` (from `detect_recurring()`) in **≥2 of the last 3 stored statements** for the same account number.

---

## Backend Changes

### 1. Alembic migration — add `recurring_candidates_json` to `StatementDB`

Create a new migration in `backend/alembic/versions/`:

```python
# Alembic migration: add recurring_candidates_json to statements
def upgrade():
    op.add_column("statements", sa.Column("recurring_candidates_json", sa.Text(), nullable=True))

def downgrade():
    op.drop_column("statements", "recurring_candidates_json")
```

Also add the field to `StatementDB` in `backend/app/db/models.py`:
```python
recurring_candidates_json: Optional[str] = None  # JSON list from detect_recurring()
```

### 2. Store recurring candidates in `save_statement()` — `backend/app/db/crud.py`

Modify `save_statement()` to accept an optional `recurring_candidates` parameter:

```python
def save_statement(
    session: Session,
    file_hash: str,
    filename: str,
    result: dict,
    recurring_candidates: list | None = None,
) -> StatementDB:
    ...
    stmt = StatementDB(
        ...
        recurring_candidates_json=json.dumps(recurring_candidates or []),
    )
```

### 3. Pass recurring candidates from analyze router — `backend/app/routers/analyze.py`

After `detect_recurring()` is called (already there from BSA-07 lite), pass the result to `save_statement()`:

```python
if persist:
    save_statement(
        session, file_hash, file.filename, result,
        recurring_candidates=result.get("result", {}).get("recurring_candidates", [])
    )
```

### 4. New CRUD function — `backend/app/db/crud.py`

```python
def get_cross_statement_recurring(account_number: str, session: Session) -> list[dict]:
    """
    Returns merchants that appear as recurring_candidates in ≥2 of the last 3
    stored statements for the given account number.
    """
    stmts = session.exec(
        select(StatementDB)
        .where(StatementDB.account_number == account_number)
        .order_by(StatementDB.uploaded_at.desc())
        .limit(3)
    ).all()

    if len(stmts) < 2:
        return []  # Need at least 2 statements to confirm

    # Collect merchant counts across statements
    merchant_appearances: dict[str, list[dict]] = {}
    for stmt in stmts:
        candidates = json.loads(stmt.recurring_candidates_json or "[]")
        for c in candidates:
            m = c.get("merchant")
            if m:
                merchant_appearances.setdefault(m, []).append(c)

    # A merchant is confirmed if it appeared in ≥2 statements
    confirmed = []
    for merchant, appearances in merchant_appearances.items():
        if len(appearances) >= 2:
            avg_amount = sum(a.get("avg_amount", 0) for a in appearances) / len(appearances)
            confirmed.append({
                "merchant": merchant,
                "statement_count": len(appearances),
                "avg_amount": round(avg_amount, 2),
                "last_seen": appearances[0].get("last_seen"),  # most recent first (desc order)
            })

    return sorted(confirmed, key=lambda x: x["statement_count"], reverse=True)
```

### 5. New endpoint — `backend/app/routers/statements.py`

```python
from app.db.crud import get_cross_statement_recurring

@router.get("/api/statements/recurring")
def get_recurring_subscriptions(
    account_number: str = Query(..., description="Account number to check for recurring charges"),
    session: Session = Depends(get_session),
):
    """
    Returns merchants confirmed as recurring across multiple stored statements
    for the given account. Requires ≥2 persisted statements.
    """
    confirmed = get_cross_statement_recurring(account_number, session)
    return {
        "account_number": account_number,
        "confirmed_recurring": confirmed,
        "requires_statements": 2,
    }
```

**Important:** Register `GET /api/statements/recurring` BEFORE `GET /api/statements/{statement_id}/transactions` to avoid FastAPI matching "recurring" as an integer.

---

## Frontend Changes

### 6. New component — `frontend/components/SubscriptionsCard.tsx`

A simple card showing confirmed recurring subscriptions:

```tsx
interface ConfirmedRecurring {
  merchant: string;
  statement_count: number;
  avg_amount: number;
  last_seen: string | null;
}

interface Props {
  subscriptions: ConfirmedRecurring[];
}

export default function SubscriptionsCard({ subscriptions }: Props) {
  if (!subscriptions.length) return null;

  const monthlyTotal = subscriptions.reduce((sum, s) => sum + s.avg_amount, 0);

  return (
    <div className="bg-white rounded-xl shadow p-6 mt-6">
      <h2 className="text-lg font-semibold mb-1">Confirmed Subscriptions</h2>
      <p className="text-sm text-gray-500 mb-4">
        Recurring charges detected across multiple statements · Est. ₹{monthlyTotal.toLocaleString("en-IN")}/mo
      </p>
      <div className="divide-y">
        {subscriptions.map((s) => (
          <div key={s.merchant} className="flex justify-between items-center py-2">
            <div>
              <span className="font-medium">{s.merchant}</span>
              <span className="text-xs text-gray-400 ml-2">
                {s.statement_count} statements
              </span>
            </div>
            <span className="text-sm font-semibold text-gray-700">
              ~₹{s.avg_amount.toLocaleString("en-IN")}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 7. API call — `frontend/services/api.ts`

```typescript
export async function getConfirmedRecurring(accountNumber: string) {
  const res = await fetch(
    `${API_BASE}/api/statements/recurring?account_number=${encodeURIComponent(accountNumber)}`
  );
  if (!res.ok) return { confirmed_recurring: [] };
  return res.json();
}
```

### 8. Wire in `App.tsx`

Fetch `getConfirmedRecurring(accountNumber)` alongside the comparison fetch. Render `<SubscriptionsCard subscriptions={confirmedRecurring} />` after `<MonthlyComparison />`.

---

## Tests to Add

**File:** `backend/tests/test_recurring.py` (new file)

Write 4 tests:
1. `test_cross_recurring_detected` — persist 2 statements with the same merchant in recurring_candidates → confirmed list contains that merchant
2. `test_cross_recurring_single_statement` — only 1 statement → empty confirmed list
3. `test_cross_recurring_different_accounts` — 2 statements with different account numbers → empty (wrong account)
4. `test_recurring_endpoint_404_on_empty` — endpoint returns empty list (not 404) when no confirmed merchants exist

---

## Constraints

- `recurring_candidates_json` is stored at persist time. Re-running the compare endpoint does NOT re-parse statements. If `recurring_candidates_json` is NULL on an old statement (uploaded before this sprint), treat it as `[]`.
- The Alembic migration must be a new file — do NOT modify the existing `9670b8f28c89` migration.
- Run `alembic upgrade head` before running tests that need the new column.
- For tests using in-memory DB, `create_db_and_tables()` will pick up the model change automatically — no migration needed in the test environment.

---

## Verification

```bash
cd backend
alembic upgrade head   # applies the new column migration
pytest tests/test_recurring.py -v   # 4 new tests pass
pytest -v                           # full suite green
```
