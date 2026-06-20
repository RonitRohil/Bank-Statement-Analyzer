# Prompt: Fix LLM Enricher Index Bug + Aggregate-After-Enrich — TD-033, TD-034

**Task:** Fix the index-mapping bug that makes BSA-04 a silent no-op, add the regression test, and make LLM-filled merchants/categories reach the aggregates.
**Sprint ref:** Sprint-03 · Tickets: TD-033 (🔴 critical), TD-034 (🟠 high)
**Review ref:** `docs/code-review.md` → CR-S2-01, CR-S2-02, CR-S2-03
**Estimated time:** 2–3 hours

---

## Why This Change Is Needed

BSA-04 (LLM categorization) shipped in Sprint-02 but **does not work**. In `llm_enricher.py` the result mapping is:

```python
txn_index = batch_indices[item["index"]]
```

`batch_input` is built with the **global** transaction index (`{"index": i}` where `i` comes from `batch_indices`), and the prompt tells the model to echo that same index back. So `item["index"]` is *already* the global index — using it as an offset into `batch_indices` double-indexes. Result: either `IndexError` (swallowed by the catch-all `except Exception` → enrichment silently does nothing) or a category written onto the wrong transaction. Because the broad `except` hides it, no error ever surfaces.

Separately (TD-034), `merchant_insights` and `confidence_summary` are computed inside `extract_transactions()` **before** enrichment runs in the router, so even once enrichment works, LLM-filled merchants/categories never reach the charts.

## Files to Read First

1. `backend-v2/app/services/llm_enricher.py` — the buggy mapping (line ~106) and the catch-all (line ~125)
2. `backend-v2/app/routers/analyze.py` — where enrichment is called, after `extract_transactions()`
3. `backend-v2/app/models/analyzer.py` — `extract_transactions()` and `TransactionPatternTrainer` (where `merchant_insights` is built)
4. `backend-v2/tests/test_analyze.py` — existing test patterns to mirror
5. `docs/testing-strategy.md` §3.1 — the enricher test spec

## Changes to Make

### 1. Fix the index mapping (`llm_enricher.py`)

Replace the result loop:

```python
# BEFORE
for item in results:
    txn_index = batch_indices[item["index"]]
    if item.get("category"):
        ...

# AFTER
for item in results:
    txn_index = item.get("index")
    if not isinstance(txn_index, int) or not (0 <= txn_index < len(transactions)):
        logger.warning("[LLM] Out-of-range index %r in batch result — skipping", txn_index)
        continue
    if item.get("category"):
        transactions[txn_index]["category"] = [item["category"]]
        transactions[txn_index]["llm_enriched"] = True
    if item.get("merchant") and not transactions[txn_index].get("merchant"):
        transactions[txn_index]["merchant"] = item["merchant"]
```

### 2. Narrow the exception handling (CR-S2-02)

Keep the resilient outer behaviour, but stop hiding programmer errors. The `KeyError`/`IndexError` paths should log loudly. Keep `ConnectError`/`HTTPStatusError`/`JSONDecodeError` as recoverable, and make the final `except Exception` log with `exc_info=True` (it already does — keep it, but ensure the new bounds-check above means it's only hit for genuinely unexpected cases).

### 3. Aggregate after enrich (TD-034)

In `analyze.py`, the cleanest fix without restructuring the analyzer: after enrichment mutates the transactions, recompute the merchant insights from the enriched list. Read how `extract_transactions()` builds `merchant_insights` (via `TransactionPatternTrainer`) and call that same path on the enriched transactions, then overwrite `result["result"]["merchant_insights"]`. If `TransactionPatternTrainer` is easily importable and callable standalone, prefer that. If not, leave a clear `# TODO TD-007` and move the enrichment call to *inside* `extract_transactions()` before the trainer runs.

State in plain English which approach you took and why before editing.

## Constraints

- Do not change the prompt or the batch-building — the input already uses global indices correctly; only the *mapping back* is wrong.
- Enrichment must still never break the endpoint (keep the non-blocking guarantee).
- Do not hit a live Ollama in tests — mock it.
- Keep the change minimal and focused; no unrelated refactors.

## Verification Steps

1. **New unit test** `backend-v2/tests/test_llm_enricher.py`:
   - Build 4 transactions, 2 with `category=[]` at global indices 1 and 3.
   - Monkeypatch the httpx call to return `[{"index": 1, "category": "Food & Dining", "merchant": "Zomato"}, {"index": 3, "category": "Travel", "merchant": null}]`.
   - Assert the category lands on transactions[1] and transactions[3] (NOT [0]/[1]), `llm_enriched=True` on both, and the already-categorized rows are untouched.
   - Add a case where the model returns an out-of-range index → assert no crash, row skipped.
2. `cd backend-v2 && pytest -m "not integration"` → all green.
3. Manual: with Ollama running, upload a CSV with unknown merchants → enriched categories appear AND the merchant shows up in `merchant_insights`.

## Commit Message

```
fix(td-033,td-034): correct LLM enricher index mapping; aggregate after enrich

- llm_enricher.py: map results by global index (was double-indexed via
  batch_indices), add bounds check, stop masking IndexError/KeyError
- analyze.py: recompute merchant_insights after enrichment so LLM-filled
  merchants/categories reach the aggregates
- tests/test_llm_enricher.py: regression test — category lands on correct txn
```

## After This Task

Update `docs/changelog.md` (root cause: double-index). Note in `docs/study/sprint-02-learnings.md` §5 that TD-033/034 are closed. Then proceed to `04-bound-enrichment.md`.
