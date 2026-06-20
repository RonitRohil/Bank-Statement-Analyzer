# Code Review — Bank Statement Analyzer

**Reviewed by:** Claude (Cowork)
**Current review:** Sprint-02 (BSA-04, BSA-05, BSA-09, BSA-10/TD-031, TD-021, parser/UI polish)
**Review date:** 2026-06-20
**Scope:** LLM enrichment service, financial summary endpoint, Flask→FastAPI cutover, FastAPI test suite, multi-page PDF fix, **and a full pass over the React/TypeScript frontend** (explicitly requested).

> Previous review (`Sprint-01`) is summarized at the bottom; full text is in git history. This review focuses on everything that landed between 2026-06-12 and 2026-06-19.

---

## Sprint-02 Completion Check

| Task | Shipped? | Notes |
|------|----------|-------|
| TD-028/029/030/032 — FastAPI housekeeping | ✅ | All four 1-liners landed (2026-06-13) |
| BSA-10 / TD-031 — FastAPI integration tests | ✅ | 7 in-process httpx tests; parity test gated behind `integration` marker |
| BSA-09 — Flask → FastAPI cutover | ✅ | Frontend `.env.local` → port 8000; Flask kept with deprecation warning |
| BSA-04 — LLM categorization fallback | ⚠️ | Shipped, but has a **critical index bug** (CR-S2-01) and is **not surfaced in the UI** |
| BSA-05 — Financial summary endpoint | ⚠️ | Shipped and correct math, but **untyped input** and **no frontend consumer** |
| TD-021 — Multi-page PDF row stitching | ✅ | `_looks_like_header()` + carried header; applied to both backends |
| Parser/UI polish (798221b) | ✅ | CSV robustness, Dr/Cr detection, metadata regex, dashboard restyle |

**Net:** Strong sprint on infrastructure and correctness. The two new *features* (BSA-04, BSA-05) both shipped backend-only and both carry defects that need a fast-follow. Nothing here should have gone to a user yet — which is fine, because no user-facing path was wired.

---

## Summary

Sprint-02 collected on the FastAPI investment: housekeeping is clean, the multi-page PDF fix closes a real data-loss bug, and the FastAPI test suite finally gives the migration a safety net. The concern is concentrated in the two new features. The LLM enricher has a real indexing bug that silently misassigns or drops every LLM category, masked by a catch-all `except`. The summary endpoint is mathematically sound but trusts an untyped `list[dict]` from the client and has no UI. And the cutover left two stale `localhost:5000` strings in the frontend that will actively mislead users now that the app talks to port 8000.

---

## Critical Issues

### CR-S2-01 🔴 LLM enricher double-indexes results onto the wrong transaction
**File:** `backend-v2/app/services/llm_enricher.py` — line 106
**Severity:** 🔴 Critical (silent incorrect data)

The batch input is built with the **global** transaction index:

```python
batch_input = [
    {"index": i, "narration": transactions[i].get("narration", "") or ""}
    for i in batch_indices            # batch_indices holds GLOBAL indices, e.g. [3, 7, 15, 42]
]
```

and the system prompt instructs the model to echo that same index back (`"index": the original index`). But the result is then mapped with:

```python
for item in results:
    txn_index = batch_indices[item["index"]]   # ← BUG: treats a global index as a batch offset
```

If the model faithfully returns `index: 42`, `batch_indices[42]` either raises `IndexError` (batch is ≤10 long) or, worse, points at an unrelated transaction. Two failure modes:

1. **IndexError** → caught by the broad `except Exception` at line 125 → the whole batch is silently dropped. Net effect: enrichment looks like it ran but changed nothing.
2. **No error but wrong target** (when the returned index happens to be < batch length) → a category lands on the wrong transaction.

Because of the catch-all, **this fails invisibly** — no user sees an error, the feature just doesn't work, and `llm_enriched` stays `False` everywhere.

**Fix (use the index directly — it's already global):**
```python
for item in results:
    txn_index = item["index"]
    if not isinstance(txn_index, int) or not (0 <= txn_index < len(transactions)):
        continue
    if item.get("category"):
        transactions[txn_index]["category"] = [item["category"]]
        transactions[txn_index]["llm_enriched"] = True
    if item.get("merchant") and not transactions[txn_index].get("merchant"):
        transactions[txn_index]["merchant"] = item["merchant"]
```

This needs a unit test that feeds a known batch and asserts the category lands on the right transaction (see `docs/testing-strategy.md`). Tracked as **TD-033**.

---

### CR-S2-02 🔴 Catch-all `except Exception` masks all enrichment failures
**File:** `backend-v2/app/services/llm_enricher.py` — lines 125–128
**Severity:** 🔴 Critical (observability)

The bare `except Exception` is what turns CR-S2-01 from a loud crash into a silent no-op. It also swallows the `KeyError`/`IndexError` you'd want surfaced during development. Keep a catch-all for *resilience* (the endpoint must never fail because the LLM did), but the handler should at minimum log at `error` with the offending payload and increment a failure counter — not blend into the background. Pair the fix with CR-S2-01 so the index bug can't hide again.

**Recommendation:** Narrow the expected-and-recoverable exceptions (`ConnectError`, `HTTPStatusError`, `JSONDecodeError`, `KeyError`, `IndexError`), and keep one final `except Exception` that logs `exc_info=True` *and* re-raises in debug mode (`settings.debug`).

---

## High-Priority Issues

### CR-S2-03 🟠 Enrichment runs *after* aggregates are computed — response is internally inconsistent
**Files:** `backend-v2/app/routers/analyze.py` (lines 51–54), `analyzer.py` (`merchant_insights`, `confidence_summary`)
**Severity:** 🟠 High (correctness)

`extract_transactions()` computes `merchant_insights` and `confidence_summary` **before** the result is returned, and `enrich_with_llm()` mutates the transactions **after** that. So when the LLM fills in a `merchant` or `category`, those values never reach the aggregates the frontend actually charts. A statement can return `transactions[i].merchant = "Zomato"` while `merchant_insights` has no Zomato entry. Once BSA-04 is fixed (CR-S2-01) this inconsistency becomes user-visible.

**Fix:** Enrich first, then aggregate. Either move enrichment inside `extract_transactions()` before `TransactionPatternTrainer` runs, or recompute `merchant_insights`/`confidence_summary` in the router after enrichment. Cleaner long-term: make enrichment a stage in the parse pipeline (ties into the TD-007 split). Tracked as **TD-034**.

### CR-S2-04 🟠 Enrichment is unbounded and blocks the request
**File:** `backend-v2/app/services/llm_enricher.py` (sequential batch loop), `analyze.py` (awaited inline)
**Severity:** 🟠 High (latency / DoS surface)

Batches run **sequentially**, each with a 60 s `httpx` timeout, inside the request the user is waiting on. A statement with 200 uncategorized rows = 20 batches × up to 60 s = a theoretical **20-minute** request with no overall deadline. There's no cap on batch count, no global timeout, and no early-exit budget. On a local Ollama this is usually fine; on any shared/hosted model it's a latency and cost footgun.

**Fix:** Add a global wall-clock budget (e.g. `asyncio.wait_for(enrich_all, timeout=settings.llm_total_timeout)`), cap the number of enriched transactions per request, and consider firing batches concurrently with a small `asyncio.Semaphore`. Tracked as **TD-035**.

### CR-S2-05 🟠 Summary endpoint trusts an untyped `list[dict]` from the client
**File:** `backend-v2/app/routers/summary.py` — `SummaryRequest.transactions: list[dict[str, Any]]`
**Severity:** 🟠 High (robustness)

The whole point of moving to Pydantic was typed contracts, but this endpoint takes raw dicts and reaches into them with `.get()`. A client sending `amount: "1,200"` (string) hits `abs(float(amount))` → `ValueError` → unhandled 500. Reuse the existing `Transaction` schema (`transactions: list[Transaction]`) so validation happens at the boundary and the handler can trust its inputs. Tracked as **TD-036**.

### CR-F2-01 🟠 Stale `localhost:5000` strings shown to users after the cutover
**Files:** `frontend/App.tsx` line 35; `frontend/services/api.ts` lines 3, 22
**Severity:** 🟠 High (user-facing correctness)

Three problems, all introduced/left by BSA-09:

1. `App.tsx:35` — network-error message hardcodes *"Ensure backend is running at http://localhost:5000"*. The app now talks to 8000. A user whose backend is down gets pointed at the wrong port.
2. `api.ts:22` — same stale port in the thrown network error.
3. `api.ts:3` — `?? 'http://localhost:5000'` fallback. `.env.local` sets 8000 so this rarely fires, but if the env var is ever missing the app silently targets the *deprecated, soon-to-be-deleted* backend.

**Fix:** Drive all three from a single constant, e.g. `const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'`, and interpolate `API_BASE` into every error string. Tracked as **TD-037**.

### CR-F2-02 🟠 BSA-04 and BSA-05 have no frontend surface
**Files:** `frontend/types.ts`, `frontend/services/api.ts`, all dashboard components
**Severity:** 🟠 High (value delivery)

`Transaction` in `types.ts` has no `llm_enriched` field, no component reads it, and there is no `getSummary()` call or summary view. Both features the sprint was built around ship invisible. This isn't a bug in the code that exists — it's the missing other half. Either wire them up in Sprint-03 (BSA-12/BSA-15 territory) or explicitly mark them "backend-only, pending UI" so it's a decision, not an oversight. Tracked as **TD-038**.

---

## Suggestions (Medium / Low)

| # | File | Suggestion | Category |
|---|------|------------|----------|
| CR-S2-06 | `summary.py` | Category percentages use `total_spend = total_expenses`, but a multi-category txn adds full spend to each category, so percentages can exceed 100%. The comment calls it intentional — at least rename the field to `pct_of_total_spend` and surface the caveat in the schema description so the frontend doesn't render a misleading pie. | Correctness |
| CR-S2-07 | `summary.py` line 58 | `total_spend = total_expenses if total_expenses > 0 else 1` — magic `1` sentinel. Guard explicitly: if no expenses, return empty `by_category` and skip the division. | Maintainability |
| CR-S2-08 | `llm_enricher.py` | `KNOWN_CATEGORIES` (LLM) and the regex categorizer's category vocabulary (`E-COMMERCE`, `FOOD_DELIVERY`, …) are **different taxonomies**. An LLM-filled `Food & Dining` won't match a regex `FOOD_DELIVERY` anywhere downstream. Unify the category vocabulary across both code paths. | Correctness |
| CR-S2-09 | `settings.py` | `ollama_model` default `qwen2.5:7b` is a hard dependency on a specific local model with no health check at startup. Log a one-line warning in `lifespan` if the Ollama endpoint isn't reachable, so the "enrichment silently did nothing" path is at least visible in logs. | Observability |
| CR-S2-10 | `main.py` | Lifespan still logs startup but not shutdown (carried CR-M-03 from Sprint-01). One line after `yield`. | Style |
| CR-S2-11 | `summary.py` | Endpoint is sync `def` (correct — pure CPU), but it's also the only place that recomputes income/expense that the frontend *also* computes in `AnalyticsCharts.tsx`. Two sources of truth for the same numbers will drift. Make the frontend consume `/summary` once it's wired. | Architecture |
| CR-F2-03 | `TransactionTable.tsx` | No virtualization — every row renders (TD-018). 500+ row statements will jank. Add pagination or `@tanstack/react-virtual` before history/multi-statement features land. | Performance |
| CR-F2-04 | `AnalyticsCharts.tsx` lines 58–66 | Income/expense reduce over `amount` assuming `DEBIT`/`CREDIT` are the only types and amounts are always positive. Mirrors backend assumptions but duplicates them. Prefer the `/summary` numbers. | Maintainability |
| CR-F2-05 | `TransactionTable.tsx` line 34 | Row key `${txn.transaction_reference}-${index}` is `null-0`, `null-1`, … when references are absent. Works (index disambiguates) but defeats React reconciliation on re-sort. Low priority since the table is currently static. | Style |
| CR-F2-06 | `AnalyticsCharts.tsx` line 74 | "Top Merchants by Volume" pie uses `count * avg_amount` as a spend proxy. Once `/summary` exists it returns real `top_merchants` totals — use those instead of reconstructing. | Correctness |
| CR-F2-07 | `types.ts` | `Transaction.amount`/`balance` typed as non-null `number`, but the backend schema marks them `Optional[float]`. A null from the API violates the TS contract at runtime. Type them `number \| null` and the components already guard with `|| 0`. | Correctness |
| CR-F2-08 | `App.tsx` line 26 | `const resAny = response as any` to read `result?.error` — the `any` escape hatch papers over a contract the `ApiResponse` type should model. Add the optional `error` field to the type. | Style |

---

## What Looks Good

- **TD-021 fix is the right shape.** `_looks_like_header()` + a carried `last_known_headers` is exactly how you stitch continuation tables without a brittle row-count heuristic. Applying it to *both* backends keeps the copies honest.
- **LLM failure is non-blocking by design.** Whatever else is wrong with the enricher, the decision that "Ollama down → return results unchanged" is correct, and `ConnectError` breaking the batch loop early is a nice touch.
- **No new pip dependency for BSA-04.** Reusing the already-present `httpx` against Ollama's OpenAI-compatible endpoint instead of pulling in `anthropic` was a pragmatic, cost-aware call. Documented in the changelog as a deliberate pivot — good.
- **Summary endpoint is honestly stateless.** Sync `def`, pure math, no I/O — and the changelog explains *why* it isn't `async`. That's the level of decision-logging this project's workflow asks for.
- **FastAPI test suite uses in-process ASGI transport.** `httpx.AsyncClient(transport=ASGITransport(...))` means CI needs no live server; the parity test that *does* need both servers is correctly fenced behind an `integration` marker. Clean separation.
- **Cutover preserved a rollback.** Flask kept alive one sprint with a `DeprecationWarning` rather than deleted outright. Reversible by design.
- **Frontend error handling is genuinely thorough.** `api.ts` distinguishes network failure, non-OK HTTP, non-JSON bodies, and deep-nested backend errors. The only problem is the stale port string, not the structure.

---

## Verdict

**Approve with required fast-follows.** Nothing here blocks the sprint from being called done — but two items must be fixed before BSA-04/BSA-05 are exposed to any user:

1. **CR-S2-01** — LLM index bug (the feature is currently a silent no-op). → TD-033
2. **CR-F2-01** — stale `localhost:5000` strings post-cutover. → TD-037

Strongly recommended in the same fast-follow: CR-S2-02 (un-mask failures), CR-S2-03 (aggregate after enrich), CR-S2-05 (type the summary input). These are all small and they're the difference between "shipped" and "works."

---

## Carried / Inherited Issues (still open)

Both backends still share these (and `analyzer.py` inherits them as a copy of `analyzeModel.py`):

- **TD-007** — `BankStatementAnalyzer` is one ~1,300-line class. The Sprint-02 features (enricher as a separate service) hint at the right direction; the core parser still needs the split.
- **TD-008** — column detection duplicated across Excel and PDF paths.
- **TD-024** — no transaction dedup (now *more* relevant: TD-021 stitches multi-page tables, raising overlap risk).
- **TD-025** — `transaction_reference` fallback regex too greedy.
- **TD-026** — confidence penalizes balance-less formats unconditionally.
- **TD-023** — upload validation trusts extension, not magic bytes.

---

## Appendix — Sprint-01 Review (archived)

The Sprint-01 review covered the FastAPI scaffold (BSA-02/03), the pytest stand-up (TD-016), and the Flask `/api/health` endpoint (TD-027). Its two critical findings (`reload=True` hardcoded, dead `import requests`) and two high findings (CORS wildcards, cwd-relative `UPLOAD_DIR`) were **all resolved** in the Sprint-02 housekeeping commit (TD-028/029/030/032). Full text in git history at `docs/code-review.md@b3f3e87`.

---

*Tech debt: `docs/tech-debt.md` · Testing: `docs/testing-strategy.md` · Study: `docs/study/sprint-02-learnings.md` · Sprint plan: `docs/sprint-03-plan.md`*
