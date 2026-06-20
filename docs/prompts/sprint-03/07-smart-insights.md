# Prompt: Smart Insights Strip (stats, no LLM) — BSA-15

**Task:** Compute plain-language insight callouts from data already in the analyze response and add them to the response + a UI strip.
**Sprint ref:** Sprint-03 · Ticket: BSA-15
**Brainstorm ref:** `docs/feature-brainstorm.md` §2.1
**Estimated time:** 3–4 hours

---

## Why This Change Is Needed

The highest perceived-intelligence-per-hour in the backlog. No LLM, no DB, no latency — just derive descriptive insights from `transactions` + `merchant_insights` that already exist. Examples: *"Top spending category: Food & Dining (32%)"*, *"Most frequent merchant: PAYTM (12×)"*, *"3 transactions above ₹10,000."*

## Files to Read First

1. `backend-v2/app/models/analyzer.py` — what `merchant_insights` and `confidence_summary` already contain
2. `backend-v2/app/routers/analyze.py` — where to attach insights (after enrichment, so it reflects enriched data — coordinate with TD-034)
3. `backend-v2/app/models/schemas.py` — add an `insights` field to the result
4. `backend-v2/app/routers/summary.py` — reuse its category/merchant math rather than re-deriving

## Changes to Make

### 1. Compute insights
Add a small pure function (e.g. `app/services/insights.py`, `generate_insights(transactions, merchant_insights) -> list[str]`). Keep each insight a short, honest, descriptive string. Suggested set:
- Top spending category + its share of spend.
- Most frequent merchant + count.
- Count of "large" transactions (above a threshold, e.g. ₹10,000 or a percentile).
- Net cash flow direction for the period ("Net positive: +₹X" / "Net negative: −₹X").
- Likely-recurring teaser (same merchant, ≥3 similar-amount hits) — the stateless half of BSA-07.

### 2. Attach to response
Add `insights: List[str] = []` to `AnalysisResult` (schemas.py). Populate it in `analyze.py` after enrichment + aggregate recompute.

### 3. Frontend strip
New `components/InsightsStrip.tsx` — a horizontal row of pill/cards above the charts. Add `insights` to the `AnalysisResult` TS type. Keep styling consistent with the existing cards.

## Constraints

- **Descriptive, not predictive.** These are stats — don't phrase them as advice or certainty. "Likely recurring," not "recurring."
- Pure functions, fully unit-testable, no I/O.
- Reuse the summary endpoint's math where it overlaps — don't re-derive category totals a third time.
- Degrade gracefully: empty/sparse statements → fewer or no insights, never a crash.

## Verification Steps

1. Unit test `test_insights.py`: known fixture → assert the expected insight strings (top category, frequent merchant, large-txn count, net direction).
2. Edge cases: single transaction; all-credit statement; empty → `insights == []`, no error.
3. Manual: upload a statement → strip shows 3–5 sensible callouts.
4. `pytest -m "not integration"` green; `npm run build` clean.

## Commit Message

```
feat(bsa-15): smart insights strip (stats-based, no LLM)

- services/insights.py: generate_insights() — top category, frequent merchant,
  large-txn count, net direction, likely-recurring teaser
- schemas.py + analyze.py: attach insights[] to result (post-enrichment)
- components/InsightsStrip.tsx: UI strip above charts
- tests/test_insights.py: fixture + edge cases
```

## After This Task

Write `docs/study/smart-insights-bsa15.md`. Update `docs/changelog.md` and mark BSA-15 done in the sprint plan.
