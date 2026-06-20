# Study Document — Sprint-03

**Sprint window:** 2026-06-20 (single intensive session)  
**Written:** 2026-06-20  
**Audience:** A developer reading this code for the first time — what was built, why every decision was made, and what to watch out for.

Sprint-02 shipped the plumbing for two features (LLM categorization, financial summary) but neither was user-visible and the enricher had a silent bug. Sprint-03's mandate was "finish before you start": close the plumbing holes, delete Flask, make both features visible in the UI, and then design — not implement — the persistence layer that gates the entire longitudinal roadmap.

---

## 1. What Was Built

Eight distinct pieces of work, in execution order:

1. **TD-033 / TD-034** — LLM enricher index bug fixed; aggregates recomputed post-enrichment
2. **TD-037** — Stale `localhost:5000` strings replaced with `API_BASE` throughout frontend
3. **TD-036** — Summary endpoint retyped with `Transaction` schema; bad input → 422 not 500
4. **TD-035** — Enrichment bounded: wall-clock budget (`asyncio.wait_for`), concurrent batches (Semaphore), cap on enriched rows
5. **CR-S2-08** — Category taxonomy unified: single `CANONICAL_CATEGORIES` list shared by regex and LLM paths; `REGEX_TO_CANONICAL` mapping; LLM prompt updated
6. **BSA-18** — Flask `backend/` deleted; `test_parity.py` deleted; CI workflow added (`.github/workflows/test.yml`)
7. **BSA-12 / TD-038** — Spending Summary card wired in frontend: `SpendingSummary.tsx`, `getSummary()` in api.ts, `SummaryResponse` types, `insights: string[]` on `AnalysisResult`
8. **BSA-15** — Smart Insights strip: `services/insights.py`, `InsightsStrip.tsx`; backend emits `insights` in analyze response
9. **ADR-002** — Persistence layer decided (SQLite via SQLModel); data model designed; `docs/adr-002-persistence.md` committed

---

## 2. Why Each Was Built

- **TD-033:** BSA-04 (LLM categorization) was shipping as a silent no-op since Sprint-02 — the index bug meant every enrichment call was either crashing silently or writing to the wrong transaction. No user had ever seen a working AI category. Fix-first, always.
- **TD-037, TD-036:** Two other fast-follows that needed to land before anything was user-exposed: stale port strings actively mislead users whose backend is down; an untyped summary endpoint returns a 500 on legitimate input.
- **TD-035:** Sequential 60-second batches × up to 20 batches = a theoretical 20-minute request. Unacceptable even for a personal tool. Fixed before exposing to any user.
- **CR-S2-08:** The regex categorizer emitted `FOOD_DELIVERY`; the LLM emitted `Food & Dining`. Nothing downstream could group or compare them. A canonical list was always required; it just hadn't been created.
- **BSA-18:** Flask's rollback window was one sprint. The suite was green, the cutover held, fast-follows were verified. Keeping two copies of `BankStatementAnalyzer` is exactly TD-007. Delete now.
- **BSA-12/TD-038:** Two Sprint-02 features were invisible to users. The Spending Summary card is the highest perceived-value-per-hour item in the backlog — income/expense/net/categories on one card.
- **BSA-15:** Smart Insights are plain-language callouts derived from data already in the response — no new backend logic needed. The perceived-intelligence-to-implementation-cost ratio is the best in the entire backlog.
- **ADR-002:** Every longitudinal feature (month-over-month, recurring detection, Q&A, learning loop) is gated on a persistence decision. That decision was being deferred sprint after sprint. Decide the design this sprint so Sprint-04 can build it.

---

## 3. How It Works — Key Code Paths

### 3.1 LLM Enricher Fix (TD-033/034/035)

**Before (broken):**

```python
txn_index = batch_indices[item["index"]]  # BUG: double-indexes
```

The prompt told the model to echo back the global transaction index. `item["index"]` was already the global index. Indexing `batch_indices` with it again produced either `IndexError` (swallowed by catch-all) or a write to the wrong row.

**After (fixed):**

```python
txn_index = item.get("index")
if not isinstance(txn_index, int) or not (0 <= txn_index < len(transactions)):
    logger.warning("[LLM] Out-of-range index %r in batch %d — skipping", ...)
    continue
```

**Bounded enrichment (TD-035):** batches now run concurrently (up to 3 at a time via `asyncio.Semaphore(3)`) inside `asyncio.wait_for(enrich_all(...), timeout=settings.llm_total_timeout_s)`. The enriched-row cap (`settings.llm_max_enriched`) limits which uncategorized indices are submitted. Partial results are returned on timeout — the endpoint always responds.

**Aggregate recompute (TD-034):** `analyze.py` now calls `TransactionPatternTrainer().analyze(enriched)` after `enrich_with_llm()` returns, overwriting `merchant_insights` with the enriched-merchant data. Before this fix, a statement with LLM-filled merchants would show them in the transactions list but not in the charts.

### 3.2 Category Taxonomy Unification (CR-S2-08)

`backend/app/services/categories.py` (new) defines two exports:

```python
CANONICAL_CATEGORIES = ["Food & Dining", "Shopping", "Entertainment", ...]

REGEX_TO_CANONICAL = {
    "FOOD_DELIVERY": "Food & Dining",
    "E-COMMERCE": "Shopping",
    "UTILITY_BILL": "Utilities",
    ...
}
```

The `CANONICAL_CATEGORIES` list is embedded in the LLM system prompt (constrains the model to only return these labels). `REGEX_TO_CANONICAL` is applied in `analyzer.py` after the regex categorizer runs, translating e.g. `FOOD_DELIVERY` → `Food & Dining`. Result: both code paths produce identical human-readable labels.

This unification was the prerequisite for the Spending Summary card to show sensible groupings — previously, a category breakdown mixing `FOOD_DELIVERY` and `Food & Dining` would show them as two separate rows.

### 3.3 Smart Insights Service (BSA-15)

`backend/app/services/insights.py` — `generate_insights()` is a pure function (no I/O, no side effects). Given `transactions` and `merchant_insights`, it returns up to 5 plain-language strings:

1. **Top spending category** — `"Top spending category: Food & Dining (32% of spend)"`
2. **Most frequent merchant** — `"Most frequent merchant: PAYTM (12×)"` — only if count ≥ 2, skips UNKNOWN
3. **Large transaction count** — `"3 transactions above ₹10,000"`
4. **Net cash flow direction** — `"Net positive: +₹4,200 for the period"` or negative
5. **Likely recurring teaser** — `"Likely recurring: NETFLIX (₹649 avg, 3×)"` — triggered when a merchant appears ≥3 times with coefficient of variation < 15% (tight amount clustering)

These are called from `analyze.py` after enrichment and added to the response under `result["result"]["insights"]`. The frontend reads `data.insights` and passes it to `InsightsStrip`.

**Why stats, not LLM:** These callouts look like AI insight but are pure descriptive statistics — no latency, no cost, no hallucination risk. The recurring teaser in particular gives a "wow" moment that costs zero compute.

### 3.4 Spending Summary Frontend (BSA-12)

`SpendingSummary.tsx` calls `getSummary(transactions)` in a `useEffect` every time the transactions array changes. It renders three big-number tiles (Income / Expenses / Net), a top-5 categories list with amounts and percentages, and a top-5 merchants list.

Key UX decision: the categories section includes a `(share of spend — may exceed 100%)` caveat inline. This is because a multi-category transaction adds its full amount to each category (e.g. a coffee that's both "Food & Dining" and "Shopping" contributes full spend to both). Without this caveat, a naive user would question the math.

`getSummary()` in `api.ts` is a separate call to `POST /api/analyze/bank/summary` — it is not derived from the analyze response. This means the summary numbers are authoritative from the backend rather than re-computed in the frontend (fixing CR-F2-04 and CR-F2-06 from the Sprint-02 review).

### 3.5 Flask Decommission (BSA-18)

`backend/` was deleted entirely. See `docs/study/flask-decommission-bsa18.md` for the full walkthrough. Key additions:

- `.github/workflows/test.yml` — `pytest` on every push + `file backend/requirements.txt | grep -qE 'ASCII|UTF-8'` guard (TD-001 regression prevention)
- `CLAUDE.md` updated to FastAPI-only framing
- `docs/architecture.md`, `docs/requirements.md` updated

### 3.6 ADR-002 — Persistence Design

Decision: **SQLite via SQLModel.** Full rationale in `docs/adr-002-persistence.md`. Three tables designed:

- `statements` — one row per upload; `file_hash` (SHA-256) is the dedup key
- `transactions` — FK to `statements`; queryable corpus for Q&A/recurring/month-over-month
- `corrections` — fingerprint-keyed user corrections for the learning loop

Implementation is BSA-19 (Sprint-04 P0). The design is done; the code is not.

---

## 4. Key Decisions & Alternatives Considered

| Decision                   | Chosen                                                  | Alternative                     | Why                                                                  |
| -------------------------- | ------------------------------------------------------- | ------------------------------- | -------------------------------------------------------------------- |
| Enrichment concurrency     | `asyncio.Semaphore(3)` — 3 concurrent batches           | Sequential (original)           | 3× faster; semaphore prevents Ollama overload                        |
| Enrichment timeout         | `asyncio.wait_for` + configurable `llm_total_timeout_s` | No timeout (original)           | Partial results > infinite wait                                      |
| Category list              | 16 canonical human-readable labels                      | Keep two separate taxonomies    | Downstream grouping requires a common key                            |
| Insights computation       | Pure function in `services/insights.py`                 | LLM-generated callouts          | Zero latency, zero cost, zero hallucination                          |
| Recurring teaser threshold | CV < 0.15 (tight cluster)                               | Fixed count + amount range      | CV handles any price point; robust to merchant variation             |
| Summary card API call      | Separate `POST /summary`                                | Re-derive from analyze response | Authoritative backend numbers; avoids duplication drift              |
| Flask deletion timing      | Now (Sprint-03)                                         | One more sprint                 | Suite green + fast-follows verified = window served its purpose      |
| Persistence ORM            | SQLModel                                                | SQLAlchemy + marshmallow        | SQLModel reuses Pydantic v2 already in stack; same author as FastAPI |

---

## 5. What To Watch Out For (Gotchas & Known Limitations)

1. **TD-035 is bounded but still slow.** The wall-clock budget prevents infinite hangs, but a statement with many uncategorized rows still waits the full `llm_total_timeout_s` before returning partial enrichment. The UX is "slow, then done" not "fast, then slow." Consider showing a loading indicator once the dashboard is streaming (BSA-11, Tier 4).

2. **Insights strip is stateless.** The recurring teaser fires on a single statement's data — 3 occurrences within one month is a weak recurring signal. The description deliberately says "Likely recurring." True cross-statement recurring detection requires persistence (BSA-07, Sprint-05).

3. **`REGEX_TO_CANONICAL` must be kept in sync with `CANONICAL_CATEGORIES`.** If you add a new category to the LLM list, ensure the regex path can map to it via `REGEX_TO_CANONICAL`. The two lists are in the same file (`categories.py`) for exactly this reason — but the mapping isn't validated at startup.

4. **`SummaryResponse.currency` field.** `SpendingSummary.tsx` reads `summary.currency ?? "INR"` — the backend `SummaryResponse` doesn't currently emit a `currency` field, so it always falls back to INR. Fine for a single-market tool; needs attention before multi-currency support.

5. **Frontend has no test suite.** The CI frontend job runs `npm run test --if-present` which is currently a no-op. `InsightsStrip` and `SpendingSummary` have no tests. This is now the largest testing gap (see `docs/testing-strategy.md §3.2`).

6. **The empty `backend/` directory.** A failed `mkdir` during the Sprint-03 close-out session created an empty `backend/` directory on the mounted filesystem that couldn't be removed from the sandbox. Run `rmdir backend && git mv backend-v2 backend && git commit -m "BSA-20: rename backend-v2 to backend"` on your local machine to complete the rename cleanly.

---

## 6. New Files Added This Sprint

| File                                      | Purpose                                              |
| ----------------------------------------- | ---------------------------------------------------- |
| `backend/app/services/categories.py`      | Canonical 16-category list + regex→canonical mapping |
| `backend/app/services/insights.py`        | `generate_insights()` pure function                  |
| `backend/tests/test_insights.py`          | Unit tests for insights generation                   |
| `frontend/components/SpendingSummary.tsx` | Spending summary card component                      |
| `frontend/components/InsightsStrip.tsx`   | Pill-style insights strip component                  |
| `docs/adr-002-persistence.md`             | SQLite/SQLModel persistence design                   |
| `docs/study/flask-decommission-bsa18.md`  | Flask deletion study doc                             |
| `.github/workflows/test.yml`              | CI pipeline (pytest + encoding guard)                |

---

## 7. What's Next

**Sprint-04 P0 — Persistence implementation (BSA-19):** SQLite + SQLModel + Alembic. The design is in `docs/adr-002-persistence.md`. Key obligations: encryption-at-rest decision, Alembic init, dedup check in `analyze.py`, `persist=true` toggle.

**TD-038 remainder:** The spending summary card is wired (BSA-12 done). The "AI-categorized" badge on individual transaction rows is still missing — `llm_enriched` is now in the TS types but `TransactionTable.tsx` doesn't render it. Small frontend addition.

**TD-024 — Transaction dedup:** Hash on `(date, amount, narration, balance)` before scoring. Priority rises now that multi-page PDF stitching (TD-021) increases overlap risk.

**BSA-13 — Export CSV/Excel:** No prerequisites. Quick win. High user value ("I parsed the PDF to get the data out — let me download it").

Full plan: `docs/sprint-04-plan.md`.

---

_Previous study docs: `docs/study/sprint-02-learnings.md` · Review: `docs/code-review.md` · Sprint plan: `docs/sprint-04-plan.md` · ADR: `docs/adr-002-persistence.md`_
