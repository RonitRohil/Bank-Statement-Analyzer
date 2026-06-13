# Prompt: Financial Summary Endpoint — BSA-05

**Task:** Add `POST /api/analyze/bank/summary` to FastAPI — takes a transactions array, returns income/expense totals, per-category breakdown, and top merchants.  
**Sprint ref:** Sprint-02 · Ticket: BSA-05  
**Estimated time:** 1.5 hours  
**No external dependencies:** Pure Python math on the existing transaction data.

---

## Why This Change Is Needed

After uploading a statement, the user gets 150+ transactions and `merchant_insights`. But there's no "so what?" summary. The data to answer "where did my money go?" is already in the transactions array — we just don't surface it cleanly. This endpoint is a 30-line Python function that gives users immediate value.

The design is: frontend sends the transactions from the analyze response back to this endpoint, gets a summary. No state, no database, no LLM. Fast and cheap.

---

## Files to Read First

1. `backend-v2/app/routers/analyze.py` — pattern to follow for a new router
2. `backend-v2/app/models/schemas.py` — `Transaction` model, specifically `amount`, `transaction_type`, `category`, `merchant`, `transaction_date`
3. `backend-v2/app/main.py` — where routers are registered

---

## What to Build

### 1. New schema in `backend-v2/app/models/schemas.py`

Add these classes at the bottom of `schemas.py`:

```python
class CategoryBreakdown(BaseModel):
    category: str
    total: float
    count: int
    percentage: float


class TopMerchant(BaseModel):
    merchant: str
    total: float
    count: int


class SummaryResponse(BaseModel):
    total_income: float
    total_expenses: float
    net: float
    currency: str = "INR"
    date_range: Optional[StatementPeriod] = None
    by_category: list[CategoryBreakdown]
    top_merchants: list[TopMerchant]
    transaction_count: int
    avg_transaction_amount: float
```

### 2. New file `backend-v2/app/routers/summary.py`

```python
"""
Financial Summary Endpoint (BSA-05)

Accepts the transactions array from /api/analyze/bank/statement
and returns a financial summary: totals, category breakdown, top merchants.

No state. Pure math. No LLM.
"""

import logging
from collections import defaultdict
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.models.schemas import SummaryResponse, CategoryBreakdown, TopMerchant, StatementPeriod

router = APIRouter()
logger = logging.getLogger(__name__)


class SummaryRequest(BaseModel):
    transactions: list[dict[str, Any]]


@router.post("/api/analyze/bank/summary", response_model=SummaryResponse)
def summarize_transactions(body: SummaryRequest):
    transactions = body.transactions

    total_income = 0.0
    total_expenses = 0.0
    category_totals: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0})
    merchant_totals: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0})
    amounts = []
    dates = []

    for txn in transactions:
        amount = txn.get("amount")
        if not amount or amount == 0:
            continue

        txn_type = (txn.get("transaction_type") or "").upper()
        amount = abs(float(amount))
        amounts.append(amount)

        if txn_type in ("CREDIT", "CR"):
            total_income += amount
        else:
            total_expenses += amount
            # Only count expenses for category/merchant breakdown
            categories = txn.get("category") or ["Uncategorized"]
            for cat in categories:
                category_totals[cat]["total"] += amount
                category_totals[cat]["count"] += 1

            merchant = txn.get("merchant")
            if merchant:
                merchant_totals[merchant]["total"] += amount
                merchant_totals[merchant]["count"] += 1

        date = txn.get("transaction_date")
        if date:
            dates.append(date)

    net = total_income - total_expenses
    total_spend = total_expenses if total_expenses > 0 else 1  # avoid div by zero

    by_category = sorted(
        [
            CategoryBreakdown(
                category=cat,
                total=round(data["total"], 2),
                count=data["count"],
                percentage=round((data["total"] / total_spend) * 100, 1),
            )
            for cat, data in category_totals.items()
        ],
        key=lambda x: x.total,
        reverse=True,
    )

    top_merchants = sorted(
        [
            TopMerchant(
                merchant=merchant,
                total=round(data["total"], 2),
                count=data["count"],
            )
            for merchant, data in merchant_totals.items()
        ],
        key=lambda x: x.total,
        reverse=True,
    )[:10]  # Top 10 only

    date_range = None
    if dates:
        dates_sorted = sorted(dates)
        date_range = StatementPeriod(
            **{"from": dates_sorted[0], "to": dates_sorted[-1]}
        )

    return SummaryResponse(
        total_income=round(total_income, 2),
        total_expenses=round(total_expenses, 2),
        net=round(net, 2),
        date_range=date_range,
        by_category=by_category,
        top_merchants=top_merchants,
        transaction_count=len(transactions),
        avg_transaction_amount=round(sum(amounts) / len(amounts), 2) if amounts else 0.0,
    )
```

### 3. Register the new router in `backend-v2/app/main.py`

```python
from app.routers import health, analyze, summary   # add summary

# ...existing middleware...

app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(summary.router)   # ADD THIS
```

### 4. Create `backend-v2/app/routers/__init__.py` if it doesn't exist

Empty file is fine.

---

## Constraints

- This endpoint is `def` (sync) not `async def` — it's pure CPU math with no I/O, so there's no benefit to async and no need for `asyncio.to_thread`
- Do not store any state — the full input comes in the request, the full output goes in the response
- `category` on a transaction is a list — a transaction can have multiple categories. Count the spend once per category (not divided) — this is an intentional design choice so the category totals can exceed 100% in edge cases. Document this.
- Merchant totals only count expense transactions (debits), not credits
- Top 10 merchants only — cap the list to avoid huge responses

---

## Verification Steps

1. Start FastAPI: `cd backend-v2 && python run.py`
2. Go to `http://localhost:8000/docs`
3. Find `POST /api/analyze/bank/summary`
4. Send a test request:
```json
{
  "transactions": [
    {"amount": 500, "transaction_type": "DEBIT", "category": ["Food & Dining"], "merchant": "Swiggy", "transaction_date": "2024-01-05"},
    {"amount": 50000, "transaction_type": "CREDIT", "category": ["Salary"], "merchant": null, "transaction_date": "2024-01-06"},
    {"amount": 2000, "transaction_type": "DEBIT", "category": ["Shopping"], "merchant": "Amazon", "transaction_date": "2024-01-07"}
  ]
}
```
5. Expected response:
```json
{
  "total_income": 50000.0,
  "total_expenses": 2500.0,
  "net": 47500.0,
  "by_category": [
    {"category": "Shopping", "total": 2000.0, "count": 1, "percentage": 80.0},
    {"category": "Food & Dining", "total": 500.0, "count": 1, "percentage": 20.0}
  ],
  "top_merchants": [
    {"merchant": "Amazon", "total": 2000.0, "count": 1},
    {"merchant": "Swiggy", "total": 500.0, "count": 1}
  ],
  "transaction_count": 3,
  "avg_transaction_amount": 2500.0
}
```

---

## Commit Message (hand to Ronit)

```
feat(bsa-05): add POST /api/analyze/bank/summary endpoint

- routers/summary.py: new endpoint — income/expenses/net totals,
  per-category breakdown with % of spend, top 10 merchants
- models/schemas.py: CategoryBreakdown, TopMerchant, SummaryResponse
- main.py: register summary router

Pure Python math — no I/O, no LLM, no state.
Frontend can call this with the transactions array from /analyze response.
```

---

## After This Task

Update `docs/changelog.md`. Also think about: should the frontend call this automatically after analyze? Or let the user trigger it? That's a product decision — make a note in `docs/requirements.md`.
