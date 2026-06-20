# Prompt 03 — TD-024: Transaction Deduplication

## Task: Deduplicate transactions in the parser before confidence scoring

**Context:** Multi-page PDF stitching (TD-021, Sprint-02) increased overlap risk — adjacent pages may extract the same boundary row twice, inflating transaction counts and merchant totals. Now that persistence is live (BSA-19), duplicates would also land in the DB. Fix it before history-based features accumulate dirty data.

**Files to read first:**
- `backend/app/models/analyzer.py` — find `extract_transactions()` and both processor methods
- `backend/tests/test_analyze.py` — understand the existing test structure

---

## Change — Add dedup step inside `BankStatementAnalyzer`

**File:** `backend/app/models/analyzer.py`

Find `extract_transactions()` — the method that calls `_process_excel_csv()` or `_process_pdf_transactions()` and returns the final transactions list. Add a dedup pass **after** extraction, **before** confidence scoring.

### Dedup key

Use `(transaction_date, amount, narration, balance)` as a compound key. This tuple identifies a logical transaction — same date, amount, narration, and running balance cannot be two different transactions.

```python
def _deduplicate_transactions(self, transactions: list[dict]) -> list[dict]:
    """Remove exact duplicates by (date, amount, narration, balance). Keeps first occurrence."""
    seen: set[tuple] = set()
    deduped: list[dict] = []
    dropped = 0
    for txn in transactions:
        key = (
            txn.get("transaction_date"),
            txn.get("amount"),
            txn.get("narration", "")[:100],   # cap narration to avoid hash on huge strings
            txn.get("balance"),
        )
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        deduped.append(txn)
    if dropped > 0:
        logger.info("[DEDUP] Removed %d duplicate transaction(s)", dropped)
    return deduped
```

Call it inside `extract_transactions()`:

```python
# After _process_excel_csv() or _process_pdf_transactions():
transactions = self._deduplicate_transactions(transactions)
# Then: confidence scoring, merchant insights, etc.
```

**Constraints:**
- Keep the **first** occurrence of a duplicate, not the last.
- The `narration[:100]` cap is intentional — prevents memory issues with malformed rows that produce huge narration strings.
- Log at `INFO` only when duplicates are actually removed. Don't log for clean statements.
- Do not remove transactions that merely have similar-looking narrations — the key must be an exact match on all four fields.

---

## Edge Cases to Handle

1. **`None` values in the key** — `(None, 100.0, "UPI transfer", None)` is a valid key in a Python `set`. Don't convert Nones — they're structural.
2. **Float precision** — `amount` comes from `parse_amount()` which already returns a Python `float`. Floating-point equality in the set key is fine here (we're deduplicating rows extracted from the same file, not comparing across files).
3. **Empty narration** — `txn.get("narration", "")` defaults to empty string. A row with no narration is rare but valid.

---

## Tests

**File:** `backend/tests/test_analyze.py` or a new `backend/tests/test_dedup.py`

Add test cases:

1. **Exact duplicate is removed:** Feed two identical transaction dicts → output has 1.
2. **Near-duplicate is kept:** Same date + amount but different narration → both kept.
3. **None fields handled:** Two rows with `balance=None` and identical other fields → deduped to 1.
4. **Log message emitted:** When a duplicate is removed, assert `logger.info` was called (use `caplog` fixture).

---

## Documentation

1. `docs/changelog.md` — add entry for TD-024.
2. `docs/tech-debt.md` — mark TD-024 as ✅ resolved.

**Verification:**

```bash
cd backend && pytest -v
```

Create a test CSV with two identical rows. Upload via `curl` or Swagger. Response `total_transactions` should be 1, not 2.
