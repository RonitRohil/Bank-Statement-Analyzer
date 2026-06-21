# Sprint-05 Prompt 02 — Month-over-Month Comparison (BSA-17)

**Ticket:** BSA-17  
**Estimated time:** 4–5h  
**Context:** `docs/sprint-05-plan.md`, `docs/adr-002-persistence.md`  
**Prerequisite:** Prompt 01 completed (`GET /api/statements/{id}/transactions` exists)

Month-over-month comparison is the flagship feature of Sprint-05. It's the moment the product stops being a one-shot parser and starts being a financial record.

---

## Files to Read First

- `backend/app/db/models.py` — StatementDB, TransactionDB schemas
- `backend/app/db/crud.py` — existing CRUD helpers (you'll add a new query function)
- `backend/app/db/database.py` — get_session pattern
- `backend/app/routers/statements.py` — existing router (add new endpoint here)
- `backend/app/models/schemas.py` — add response models here
- `frontend/App.tsx` — how state is managed and passed to components
- `frontend/components/AnalyticsCharts.tsx` — existing Recharts usage (match the pattern)
- `frontend/services/api.ts` — existing API call pattern (add `compareStatements()` here)
- `frontend/types.ts` — add TypeScript interfaces here

---

## Backend Changes

### 1. New CRUD function — `backend/app/db/crud.py`

Add `get_monthly_summary(account_number, session)`:

```python
import json
from collections import defaultdict

def get_monthly_summary(account_number: str, session: Session) -> list[dict]:
    """
    Aggregate transactions by calendar month for a given account number.
    Returns a list of monthly summary dicts, ordered by month ascending.
    """
    # Find all statements for this account
    statements = session.exec(
        select(StatementDB).where(StatementDB.account_number == account_number)
        .order_by(StatementDB.period_from.asc())
    ).all()

    if not statements:
        return []

    monthly: dict[str, dict] = {}  # key: "YYYY-MM"

    for stmt in statements:
        txns = session.exec(
            select(TransactionDB).where(TransactionDB.statement_id == stmt.id)
        ).all()

        for txn in txns:
            if not txn.transaction_date:
                continue
            month_key = txn.transaction_date[:7]  # "YYYY-MM"
            if month_key not in monthly:
                monthly[month_key] = {
                    "month": month_key,
                    "income": 0.0,
                    "expenses": 0.0,
                    "net": 0.0,
                    "transaction_count": 0,
                    "category_totals": defaultdict(float),
                }
            m = monthly[month_key]
            amount = abs(txn.amount or 0.0)
            txn_type = (txn.transaction_type or "").upper()
            m["transaction_count"] += 1
            if txn_type in ("CREDIT", "CR"):
                m["income"] += amount
            else:
                m["expenses"] += amount
                cats = json.loads(txn.category or "[]")
                for cat in cats:
                    m["category_totals"][cat] += amount

    # Build result list sorted by month
    result = []
    months_sorted = sorted(monthly.keys())
    for i, month_key in enumerate(months_sorted):
        m = monthly[month_key]
        net = round(m["income"] - m["expenses"], 2)
        # Top category by spend
        top_cat = max(m["category_totals"], key=m["category_totals"].get) if m["category_totals"] else None
        # Delta vs previous month
        delta = None
        if i > 0:
            prev_exp = monthly[months_sorted[i-1]]["expenses"]
            if prev_exp > 0:
                delta = round(((m["expenses"] - prev_exp) / prev_exp) * 100, 1)
        result.append({
            "month": month_key,
            "income": round(m["income"], 2),
            "expenses": round(m["expenses"], 2),
            "net": net,
            "transaction_count": m["transaction_count"],
            "top_category": top_cat,
            "delta_expenses_pct": delta,  # % change vs previous month; null for first month
        })

    return result
```

### 2. New response schema — `backend/app/models/schemas.py`

Add after existing models:

```python
class MonthSummary(BaseModel):
    month: str                          # "YYYY-MM"
    income: float
    expenses: float
    net: float
    transaction_count: int
    top_category: Optional[str] = None
    delta_expenses_pct: Optional[float] = None  # % change vs. previous month

class ComparisonResponse(BaseModel):
    account_number: str
    months: list[MonthSummary]
    total_months: int
```

### 3. New endpoint — `backend/app/routers/statements.py`

Add after the existing endpoints:

```python
from app.db.crud import get_monthly_summary
from app.models.schemas import ComparisonResponse, MonthSummary

@router.get("/api/statements/compare", response_model=ComparisonResponse)
def compare_statements(
    account_number: str = Query(..., description="Account number to compare across statements"),
    session: Session = Depends(get_session),
):
    """
    Returns month-over-month financial summary for a given account number.
    Requires at least one stored statement with persist=true.
    """
    months = get_monthly_summary(account_number, session)
    if not months:
        raise HTTPException(
            status_code=404,
            detail=f"No statements found for account {account_number}",
        )
    return ComparisonResponse(
        account_number=account_number,
        months=months,
        total_months=len(months),
    )
```

**Important:** Register this endpoint BEFORE `GET /api/statements/{statement_id}/transactions` in the router or FastAPI will try to match `"compare"` as a `statement_id` integer. Put `compare` before `{statement_id}`.

---

## Frontend Changes

### 4. New API function — `frontend/services/api.ts`

Add:

```typescript
export interface MonthSummary {
  month: string;               // "YYYY-MM"
  income: number;
  expenses: number;
  net: number;
  transaction_count: number;
  top_category: string | null;
  delta_expenses_pct: number | null;
}

export interface ComparisonResponse {
  account_number: string;
  months: MonthSummary[];
  total_months: number;
}

export async function compareStatements(accountNumber: string): Promise<ComparisonResponse> {
  const res = await fetch(
    `${API_BASE}/api/statements/compare?account_number=${encodeURIComponent(accountNumber)}`
  );
  if (!res.ok) throw new Error(`Compare failed: ${res.status}`);
  return res.json();
}
```

### 5. New types — `frontend/types.ts`

Add `MonthSummary` and `ComparisonResponse` interfaces (mirror from `api.ts`).

### 6. New component — `frontend/components/MonthlyComparison.tsx`

```tsx
import { ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { MonthSummary } from "../types";

interface Props {
  months: MonthSummary[];
  accountNumber: string;
}

export default function MonthlyComparison({ months, accountNumber }: Props) {
  if (!months.length) return null;

  const data = months.map((m) => ({
    name: m.month,          // "YYYY-MM" — Recharts uses this as X label
    Income: m.income,
    Expenses: m.expenses,
    Net: m.net,
  }));

  return (
    <div className="bg-white rounded-xl shadow p-6 mt-6">
      <h2 className="text-lg font-semibold mb-1">Month-over-Month</h2>
      <p className="text-sm text-gray-500 mb-4">Account: {accountNumber}</p>

      {months.length === 1 && (
        <p className="text-xs text-amber-600 mb-3">
          Upload more statements to see trends. Showing single-month data.
        </p>
      )}

      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data}>
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `₹${(v/1000).toFixed(0)}k`} />
          <Tooltip formatter={(v: number) => `₹${v.toLocaleString("en-IN")}`} />
          <Legend />
          <Bar dataKey="Income" fill="#4ade80" radius={[4,4,0,0]} />
          <Bar dataKey="Expenses" fill="#f87171" radius={[4,4,0,0]} />
          <Line type="monotone" dataKey="Net" stroke="#6366f1" strokeWidth={2} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Delta row */}
      <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
        {months.slice(-4).map((m) => (
          <div key={m.month} className="rounded-lg bg-gray-50 p-3 text-center">
            <div className="text-xs text-gray-500">{m.month}</div>
            <div className="font-semibold text-sm">₹{m.expenses.toLocaleString("en-IN")}</div>
            {m.delta_expenses_pct !== null && (
              <div className={`text-xs ${m.delta_expenses_pct > 0 ? "text-red-500" : "text-green-600"}`}>
                {m.delta_expenses_pct > 0 ? "▲" : "▼"} {Math.abs(m.delta_expenses_pct)}%
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 7. Wire into `frontend/App.tsx`

The component should only render when:
- The current analysis result has an `account_info.account_number`
- There are stored statements (fetch `GET /api/statements` after a successful persist upload to check)

Add a `useEffect` that calls `compareStatements(accountNumber)` when `accountInfo.account_number` is set and `persist` mode is on. Store the result in `comparisonData` state. Pass it to `<MonthlyComparison months={comparisonData.months} accountNumber={...} />` rendered below the charts section.

**Note:** Don't fetch on every render — fetch once after upload completes. If `accountNumber` is null/missing from the parsed statement, skip the comparison fetch silently.

---

## Tests to Add

**File:** `backend/tests/test_comparison.py` (new file)

```python
# test_comparison.py
import pytest

class TestMomComparison:
    def test_compare_single_month(self, client, db_session):
        # Persist a statement, then hit /api/statements/compare?account_number=...
        # Expect 1 month in response, delta_expenses_pct = null

    def test_compare_two_months(self, client, db_session):
        # Persist 2 statements with different period_from months
        # Expect 2 months, second month has delta_expenses_pct set

    def test_compare_404_unknown_account(self, client, db_session):
        # GET /api/statements/compare?account_number=NOTEXIST → 404

    def test_compare_no_account_param(self, client):
        # GET /api/statements/compare (missing query param) → 422
```

Write the actual test bodies, don't just scaffold. Use in-memory DB fixture from `conftest.py`.

---

## Constraints

- The `GET /api/statements/compare` endpoint must be registered **before** `GET /api/statements/{statement_id}/transactions` in the router to avoid FastAPI treating "compare" as an integer ID.
- `delta_expenses_pct` is `null` (Python `None`) for the first month in the series — do not default to 0.
- If `account_number` is `None` on a `StatementDB` row (extraction failed), that statement is excluded from the comparison. Do not crash.
- Keep Recharts imports to what's already in `AnalyticsCharts.tsx` — don't install a new charting library.

---

## Verification

```bash
cd backend
pytest tests/test_comparison.py -v    # all 4 tests pass
pytest -v                              # full suite green (~45 tests)
```

Manual test:
1. Start backend + frontend
2. Upload two statements from different months with `persist=true` (add a UI checkbox or use curl: `curl -X POST .../statement?persist=true -F "file=@..."`)
3. Navigate to the frontend → `MonthlyComparison` chart should appear below the charts section with two bars
