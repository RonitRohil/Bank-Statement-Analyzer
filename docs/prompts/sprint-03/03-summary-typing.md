# Prompt: Type the Summary Endpoint Input — TD-036

**Task:** Replace the untyped `list[dict]` input on the summary endpoint with the existing `Transaction` schema, and add a unit test.
**Sprint ref:** Sprint-03 · Ticket: TD-036
**Review ref:** `docs/code-review.md` → CR-S2-05, CR-S2-06, CR-S2-07
**Estimated time:** 30–45 minutes

---

## Why This Change Is Needed

`backend-v2/app/routers/summary.py` defines `SummaryRequest.transactions: list[dict[str, Any]]` and reaches into the dicts with `.get()`. A client sending `amount: "1,200"` (string) reaches `abs(float(amount))` → unhandled `ValueError` → 500. The whole point of Pydantic is to validate at the boundary; this endpoint opts out of it.

## Files to Read First

1. `backend-v2/app/routers/summary.py` — the request model and the math loop
2. `backend-v2/app/models/schemas.py` — the existing `Transaction`, `SummaryResponse`, `CategoryBreakdown`, `TopMerchant` models
3. `docs/testing-strategy.md` §3.1 — the summary test spec

## Changes to Make

### 1. Use the typed model

```python
from app.models.schemas import Transaction  # already defined

class SummaryRequest(BaseModel):
    transactions: list[Transaction]
```

Update the loop to read attributes off the model (`txn.amount`, `txn.transaction_type`, `txn.category`, `txn.merchant`, `txn.transaction_date`) instead of `.get(...)`. Pydantic now guarantees `amount` is `float | None`, so the string-amount 500 disappears (a bad amount → 422 at the boundary).

### 2. Clean up the magic sentinel (CR-S2-07)

```python
# BEFORE
total_spend = total_expenses if total_expenses > 0 else 1

# AFTER
if total_expenses <= 0:
    # no expenses → empty category breakdown, skip percentage math
    by_category = []
else:
    ... # existing breakdown with percentage = total / total_expenses * 100
```

### 3. Document the >100% caveat (CR-S2-06)

Add a field description on `SummaryResponse.by_category` (or a module docstring) noting that multi-category transactions count full spend toward each category, so percentages can sum to >100%. This tells the frontend not to render it as a naive 100%-pie.

## Constraints

- Reuse the existing `Transaction` schema — do **not** define a parallel model.
- Keep the endpoint sync `def` (it's pure CPU; correct as-is).
- Preserve current output shape (`SummaryResponse`) — only the input typing and the sentinel change.

## Verification Steps

1. **New unit test** `backend-v2/tests/test_summary.py`:
   - Known 5-transaction fixture → assert `total_income`, `total_expenses`, `net`, top-merchant order, `avg_transaction_amount`, `date_range`.
   - Empty `transactions: []` → all zeros, `by_category == []`, no exception.
   - `amount: "oops"` → POST returns **422**, not 500 (validation rejects it).
2. `cd backend-v2 && pytest -m "not integration"` → green.

## Commit Message

```
fix(td-036): type summary endpoint input with Transaction schema

- summary.py: SummaryRequest.transactions: list[Transaction] (was list[dict])
- summary.py: replace magic total_spend=1 sentinel with explicit empty-case
- schemas.py: document >100% category-percentage caveat
- tests/test_summary.py: math fixture + empty + bad-amount(422) cases
```

## After This Task

Update `docs/changelog.md`. Proceed to `04-bound-enrichment.md`.
