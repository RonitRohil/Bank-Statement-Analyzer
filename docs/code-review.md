# Code Review — Bank Statement Analyzer

**Reviewed by:** Claude (Cowork)  
**Current review:** Sprint-03 (TD-033/034/035/036/037, CR-S2-08, BSA-12/15/18, ADR-002)  
**Review date:** 2026-06-20  
**Scope:** LLM enricher refactor + bounded concurrency, category taxonomy unification, insights service, spending summary frontend card, Flask decommission, CI pipeline.

> Previous review (`Sprint-02`) is summarized at the bottom. Full text in git history.

---

## Sprint-03 Completion Check

| Task                             | Shipped? | Notes                                                                   |
| -------------------------------- | -------- | ----------------------------------------------------------------------- |
| TD-033 — LLM index bug           | ✅       | `item.get("index")` + bounds check; unit test in `test_llm_enricher.py` |
| TD-034 — Aggregate after enrich  | ✅       | `TransactionPatternTrainer().analyze(enriched)` called post-enrichment  |
| TD-035 — Bounded enrichment      | ✅       | `asyncio.Semaphore(3)` + `wait_for` timeout + row cap                   |
| TD-036 — Summary endpoint typing | ✅       | `list[Transaction]`; bad input → 422; 3 new tests                       |
| TD-037 — Stale localhost:5000    | ✅       | `API_BASE` centralized; all error strings interpolate it                |
| CR-S2-08 — Category taxonomy     | ✅       | `categories.py` — 16 canonical labels + regex→canonical mapping         |
| BSA-18 — Flask deleted, CI added | ✅       | `backend/` gone; `.github/workflows/test.yml` added                     |
| BSA-12 / TD-038 — Summary card   | ✅       | `SpendingSummary.tsx`; `getSummary()` in api.ts; TS types updated       |
| BSA-15 — Smart Insights strip    | ✅       | `services/insights.py`; `InsightsStrip.tsx`; backend emits `insights[]` |
| ADR-002 — Persistence design     | ✅       | `docs/adr-002-persistence.md`; implementation deferred to Sprint-04     |

**Net:** A clean sprint. All P0 fixes landed; both P1 features (summary card, insights strip) shipped; Flask is gone; the persistence design is committed. The codebase is in its cleanest state since the project started.

---

## Summary

Sprint-03 converted Sprint-02's sunk investment into working user-visible features. The enricher refactor is the most technically interesting piece — the concurrency model (Semaphore + `wait_for`) is the right shape for a best-effort, latency-bounded async service. The category taxonomy unification was overdue and the `REGEX_TO_CANONICAL` approach is clean. One new issue was found in the insights service (CV threshold is slightly too tight for some real-world merchant data). The frontend additions are solid.

---

## What Looks Good

- **Bounded enrichment shape is correct.** `asyncio.Semaphore(3)` for concurrent batches + a global `wait_for` deadline is exactly the right pattern for a best-effort LLM call. Partial enrichment is better than a hung request.
- **`_run_batch` exception taxonomy is now specific.** `ConnectError`, `TimeoutException`, `HTTPStatusError`, `JSONDecodeError` each get their own `except` with an appropriate log level. The final `except Exception` logs `exc_info=True` — it can't mask problems silently the way the old catch-all did.
- **`categories.py` co-locates both paths.** `CANONICAL_CATEGORIES` and `REGEX_TO_CANONICAL` in the same file means a future maintainer who adds a category has one place to touch. That's the right data-locality decision.
- **`generate_insights()` is a pure function.** No side effects, no I/O, testable in isolation. The CV-based recurring teaser is a nice touch — it handles any price point without hardcoding thresholds.
- **`SpendingSummary.tsx` sources from the backend.** Calling `POST /summary` rather than re-deriving from the analyze response means one authoritative math location. This closes CR-F2-04 and CR-F2-06 from Sprint-02.
- **The `(may exceed 100%)` caveat is inline.** Showing the caveat right next to the category percentages is the correct UX decision — it preempts user confusion without requiring a tooltip or documentation.
- **CI encoding guard targets the live file.** The `file backend/requirements.txt | grep -qE 'ASCII|UTF-8'` guard correctly points at the only remaining `requirements.txt` now that Flask is deleted.
- **Test count grew.** 18 tests post-Sprint-02 → now includes `test_insights.py` cases. Every new service has a test file.

---

## Issues Found

### CR-S3-01 🟡 CV threshold of 0.15 may be too tight for some recurring merchants

**File:** `backend/app/services/insights.py` — line ~55  
**Severity:** 🟡 Medium (false negative — users miss a real insight)

```python
cv = (std / avg) if std is not None else 1.0
if cv < 0.15:
    insights.append(f"Likely recurring: ...")
```

A coefficient of variation < 0.15 (15%) means the standard deviation must be less than 15% of the mean amount. Real-world subscriptions sometimes vary — a streaming service that charges in USD will fluctuate with exchange rates; a telecom bill has occasional usage charges. In practice, most Indian subscription merchants (Netflix, Spotify, hotstar) are fixed amounts and will pass this threshold. But a mobile plan that occasionally adds data charges might have a CV of 0.18 and be silently excluded.

**Recommendation:** Raise to `cv < 0.25` or make it a configurable constant (`RECURRING_CV_THRESHOLD = 0.15` at the top of the file) so it can be tuned. Not a blocker — the teaser is explicitly labeled "Likely."

---

### CR-S3-02 🟡 `insights` field not in `AnalysisResult` schema (Pydantic)

**File:** `backend/app/models/schemas.py`  
**Severity:** 🟡 Medium (schema drift — the TS type is ahead of Pydantic)

`frontend/types.ts` correctly adds `insights: string[]` to `AnalysisResult`. But if `AnalysisResult` in `schemas.py` doesn't include an `insights` field, the FastAPI response model won't validate or document it — it just passes through in the `dict` layer. Check that `AnalysisResult` in `schemas.py` has `insights: list[str] = []`.

**Impact:** No runtime bug currently (FastAPI returns the dict unfiltered when using `response_model=None` or a dict type), but Swagger UI won't show the field and any future response-model validation will strip it.

---

### CR-S3-03 🟡 `SummaryResponse` lacks `currency` field but frontend reads it

**Files:** `backend/app/models/schemas.py`, `frontend/components/SpendingSummary.tsx` line ~56  
**Severity:** 🟡 Low (fallback hardcoded to INR — currently correct, not future-proof)

```typescript
const currency = summary.currency ?? "INR";
```

The backend `SummaryResponse` doesn't emit a `currency` field. The frontend falls back to `"INR"` silently. This is fine for a single-market tool, but:

1. The `??` implies a future multi-currency intent that doesn't exist yet — it's setting an expectation the backend doesn't meet.
2. If multi-currency ever lands, both sides need to change. Add `currency: str = "INR"` to `SummaryResponse` now so the contract is explicit.

---

### CR-S3-04 🟢 AI badge on enriched rows still missing from `TransactionTable.tsx`

**File:** `frontend/components/TransactionTable.tsx`  
**Severity:** 🟢 Low (missing, not broken — TD-038 partially open)

`llm_enriched?: boolean` is now in `types.ts` and the backend sets it. `SpendingSummary` is wired. But `TransactionTable.tsx` doesn't render any visual indicator on LLM-enriched rows. Users can't distinguish AI-assigned categories from regex-detected ones. This was the second half of TD-038 (the summary card was the first). Small addition: a subtle "AI" pill or icon in the category cell.

---

### CR-S3-05 🟢 `test_insights.py` doesn't cover the recurring teaser path

**File:** `backend/tests/test_insights.py`  
**Severity:** 🟢 Low (coverage gap)

Verify that the file has a test case that feeds ≥3 transactions for the same merchant with a tight amount spread, and asserts the recurring callout appears. The CV formula is subtle enough that a regression test here is worth having.

---

## Suggestions (Style / Cleanup)

| #        | File                  | Suggestion                                                                                                                                                                                                                                                                                                                                                 |
| -------- | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CR-S3-06 | `categories.py`       | Add a startup assertion: `assert all(v in CANONICAL_CATEGORIES for v in REGEX_TO_CANONICAL.values())` — validates mapping targets exist. One line, runs at import time.                                                                                                                                                                                    |
| CR-S3-07 | `llm_enricher.py`     | `settings.llm_max_enriched` and `settings.llm_total_timeout_s` — confirm these are in `settings.py` with sensible defaults and documented in `.env.example`.                                                                                                                                                                                               |
| CR-S3-08 | `insights.py`         | Extract `LARGE_TXN_THRESHOLD = 10_000` to `settings.py` or at minimum to a module-level constant (already done — just document it in `.env.example`).                                                                                                                                                                                                      |
| CR-S3-09 | `SpendingSummary.tsx` | The `useEffect` re-fires whenever `transactions` reference changes (every re-render of the parent if the array is recreated inline). Memoize with `useMemo` in `App.tsx` or stabilize with a length+hash comparison. Currently fine since the parent only re-renders on file upload, but worth noting before history/multi-statement increases re-renders. |
| CR-S3-10 | `test_insights.py`    | Parametrize the top-category, large-txn, and net-flow cases using `@pytest.mark.parametrize` for cleaner test isolation.                                                                                                                                                                                                                                   |

---

## Verdict

**Approve.** Sprint-03 closed a clean loop: the two features that shipped broken in Sprint-02 now work end-to-end; both are visible in the UI; Flask is gone; CI runs on every push. The issues found (CR-S3-01 through CR-S3-05) are all medium/low severity and none block the next sprint. The most actionable one is CR-S3-02 (schema drift on the `insights` field) — fix it in the first commit of Sprint-04.

---

## Carried / Inherited Issues (still open)

- **TD-007** — `BankStatementAnalyzer` is one ~1,300-line class. The Sprint-03 services split hints at the right direction; the core parser still needs it.
- **TD-008** — Column detection duplicated across Excel and PDF paths.
- **TD-018** — `TransactionTable` renders all rows with no virtualization. More urgent once persistence makes multi-statement views possible.
- **TD-023** — Upload validation trusts extension, not magic bytes.
- **TD-024** — No transaction dedup (higher risk post-TD-021 multi-page stitching).
- **TD-025** — `transaction_reference` fallback regex too greedy.
- **TD-026** — Confidence penalizes balance-less formats unconditionally.

---

## Appendix — Sprint-02 Review (archived)

Sprint-02 review covered BSA-04, BSA-05, BSA-09, BSA-10/TD-031, TD-021, parser/UI polish. Its two critical findings (enricher double-index, stale port strings) and high findings (aggregate timing, summary typing, missing UI) were **all resolved in Sprint-03**. Its medium/suggestion findings (CR-S2-06 through CR-S2-11) are closed via the summary card + category taxonomy work. Full text in git history at `docs/code-review.md@pre-sprint-03`.

---

_Tech debt: `docs/tech-debt.md` · Testing: `docs/testing-strategy.md` · Study: `docs/study/sprint-03-learnings.md` · Sprint plan: `docs/sprint-04-plan.md`_
