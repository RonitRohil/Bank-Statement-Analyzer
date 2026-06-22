# Technical Debt Report — Bank Statement Analyzer

**Original:** 2026-05-29 · **Updated:** 2026-06-22 (post-Sprint-05: MoM comparison, cross-statement recurring, analyzer split)
**Reviewed by:** Claude (Cowork)
**Project:** Bank Statement Analyzer (FastAPI/React/TypeScript)

Severity scale: 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low  
Status: ✅ Resolved · ⚠️ Reopened · ⬜ Open

---

## Status Snapshot (post-Sprint-05)

| Resolved ✅                                                                                         | Open ⬜                                 |
| --------------------------------------------------------------------------------------------------- | --------------------------------------- |
| TD-001–006, 009–015, 017, 020–022, 024, 027–041; BSA-07-full; CR-S3-01, CR-S3-05; CR-S4-01/02/03/05 | TD-018, 019, 023, 025, 026; CR-S5-01–07 |

**38 resolved, 12 open (7 net-new from Sprint-05 review). TD-007/008 and BSA-07-full closed this sprint.**

> **Sprint-05 closed:**
>
> - **TD-007/008 ✅** — Analyzer split complete. `parsers/excel_parser.py` (466 lines), `parsers/pdf_parser.py` (286 lines), `enrichers/narration_enricher.py` (271 lines), `scorers/confidence_scorer.py` (32 lines). `analyzer.py` now 299 lines (was ~1,280). All tests pass with no changes.
> - **BSA-07-full ✅** — Cross-statement recurring: `recurring_candidates_json` column on `StatementDB` (new Alembic migration `a1b2c3d4e5f6`), `get_cross_statement_recurring()` in `crud.py`, `GET /api/statements/recurring`, `SubscriptionsCard.tsx`. 4 tests in `test_recurring.py`.
> - **BSA-17 ✅** — Month-over-month comparison: `get_monthly_summary()` in `crud.py`, `GET /api/statements/compare`, `MonthSummary` + `ComparisonResponse` schemas, `MonthlyComparison.tsx` (Recharts ComposedChart). 4 tests in `test_comparison.py`.
> - **CR-S4-01 ✅** — `GET /api/statements` now accepts `limit`/`offset` (default 20, max 100).
> - **CR-S4-02 ✅** — `GET /api/statements/{id}/transactions` endpoint added (paginated, 404 on unknown).
> - **CR-S4-03 ✅** — CorrectionDB fingerprint format documented in `crud.py` comment.
> - **CR-S4-05 ✅** — Export `filename` sanitized via `re.sub(r"[^\w\-.]", "_", ...)` before `Content-Disposition`.
>
> **Sprint-05 opened (from code review CR-S5-01 through CR-S5-07):**
>
> - CR-S5-01 🟡 — Named route ordering fragile in `statements.py` (comment missing)
> - CR-S5-02 🟢 — `top_category` from MoM response not rendered in `MonthlyComparison.tsx`
> - CR-S5-03 🟢 — Parser import coupling: `pdf_parser` imports shared utils from `excel_parser`
> - CR-S5-04 🟢 — `recurring_candidates_json` staleness not documented in `crud.py`
> - CR-S5-05 🟠 — `get_monthly_summary()` loads all transactions without a limit
> - CR-S5-06 🟢 — MoM YAxis formatter breaks on sub-₹1k amounts
> - CR-S5-07 🟢 — `SubscriptionsCard` monthly total assumes all subscriptions are monthly

---

---

## Sprint-05 New Debt (opened 2026-06-22, from Sprint-05 code review)

### CR-S5-05 ⬜ 🟠 `get_monthly_summary()` loads all transactions without a cap

**File:** `backend/app/db/crud.py` — `get_monthly_summary()`
**Description:** For each stored statement matching the account, all `TransactionDB` rows are loaded into memory with no limit. A statement with 2,000 transactions × 12 stored statements = 24,000 objects loaded per comparison query. Fine for a single user with 3 statements today, but will degrade as BSA-20 (history UI) encourages more uploads.
**Fix:** Add `.limit(5000)` to the inner transaction query, or stream in configurable pages.
**Effort:** 30 min.

### CR-S5-01 ⬜ 🟡 Named route ordering fragile in `statements.py` — missing comment

**File:** `backend/app/routers/statements.py`
**Description:** `GET /api/statements/compare` and `GET /api/statements/recurring` must be declared before `GET /api/statements/{statement_id}/transactions`. FastAPI matches first-wins; adding a new named route below the parametric route would cause 422 with no obvious error. Currently correct, but no comment warns future developers.
**Fix:** Add `# NOTE: named routes (/compare, /recurring) must appear before /{statement_id}` above the parametric route.
**Effort:** 2 min.

### CR-S5-04 ⬜ 🟢 `recurring_candidates_json` staleness not documented

**File:** `backend/app/db/crud.py` — `save_statement()`
**Description:** The column stores BSA-07 lite output frozen at upload time. Future threshold changes don't update existing rows. No comment explains this design decision — a developer might try to "refresh" the column and be confused.
**Fix:** Add comment: `# Frozen at upload time. Re-upload the statement to refresh recurring detection.`
**Effort:** 2 min.

### CR-S5-03 ⬜ 🟢 `pdf_parser.py` imports shared utilities from `excel_parser.py`

**File:** `backend/app/parsers/pdf_parser.py` imports 5 functions from `excel_parser.py`
**Description:** Shared parsing utilities (`parse_amount`, `find_column`, `normalize_date`, `deduplicate_transactions`, `clean_column_name`) live in `excel_parser.py` and are imported by `pdf_parser.py`. The naming implies Excel-specific, but the functions are generic. If `excel_parser.py` is restructured, `pdf_parser.py` breaks.
**Fix:** Create `parsers/utils.py` and move the shared utilities there. Both parsers import from `utils`.
**Effort:** 1–2h.

### CR-S5-02 ⬜ 🟢 `top_category` from MoM response not rendered in frontend

**File:** `frontend/components/MonthlyComparison.tsx`
**Description:** `MonthSummary.top_category` is computed and returned by the API but `MonthlyComparison.tsx` doesn't display it. Each month's tile only shows expenses.
**Fix:** Add `top_category` label below the expense figure in each tile. Handle `null` with a dash.
**Effort:** 30 min.

### CR-S5-06 ⬜ 🟢 MoM chart YAxis formatter breaks on sub-₹1k amounts

**File:** `frontend/components/MonthlyComparison.tsx`
**Description:** `tickFormatter={(v) => \`₹${(v / 1000).toFixed(0)}k\`}` produces `₹0k` for any value under ₹1,000.
**Fix:** Conditional: `v >= 1000 ? \`₹${(v/1000).toFixed(1)}k\` : \`₹${v}\``
**Effort:** 10 min.

### CR-S5-07 ⬜ 🟢 `SubscriptionsCard` monthly cost total assumes all charges are monthly

**File:** `frontend/components/SubscriptionsCard.tsx`
**Description:** Sums all `avg_amount` values and labels the total "/mo". A quarterly insurance premium or annual fee inflates the monthly estimate.
**Fix:** Add caveat text "Est. based on detected frequency" next to the total, or remove the total until cadence detection is implemented.
**Effort:** 15 min.

---

## BSA-07-full ✅ Cross-statement recurring detection — FIXED 2026-06-22 (Sprint-05)

**Ticket:** BSA-07-full  
**Fix:** Alembic migration adds `recurring_candidates_json: Optional[str]` to `StatementDB`. `save_statement()` now accepts `recurring_candidates` and serializes to JSON. `get_cross_statement_recurring()` in `crud.py` loads last 3 statements for the account, parses JSON, and confirms merchants appearing in ≥2 as `confirmed_recurring`. `GET /api/statements/recurring` endpoint + `RecurringResponse` schema + `SubscriptionsCard.tsx` frontend component. 4 tests in `test_recurring.py`.

---

## Priority 1 — Fix Before Next Sprint

### TD-028 ✅ 🔴 `reload=True` hardcoded in `backend-v2/run.py` — **FIXED 2026-06-13**

**File:** `backend-v2/run.py` line 3  
**Score:** Impact 5 · Risk 5 · Effort 1 → **Priority 50**  
**Description:** `uvicorn.run(..., reload=True)` is hardcoded — the same class of mistake as `debug=True` in the original Flask `run.py`. In production, `reload=True` starts a file-watching subprocess, causes double-startup on some platforms, and exposes server internals.  
**Fix:**

```python
import os
reload = os.getenv("UVICORN_RELOAD", "false").lower() == "true"
uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=reload)
```

**Effort:** 2 minutes. Fix this in the same commit as TD-029.

---

### TD-029 ✅ 🔴 Dead `import requests` in `backend-v2/analyzer.py` + dead dep in requirements — **FIXED 2026-06-13**

**Files:** `backend-v2/app/models/analyzer.py` line 7, `backend-v2/requirements.txt`  
**Score:** Impact 3 · Risk 4 · Effort 1 → **Priority 35**  
**Description:** `requests` was the only dependency of `verify_bank_account_with_pennyless()`, which was deleted from Flask. The import was never removed from the FastAPI copy. `requests==2.32.5` also stays in `backend-v2/requirements.txt` unnecessarily. Dead imports are noise and unused deps are attack surface.  
**Fix:** Remove `import requests` from `analyzer.py` line 7. Remove `requests==2.32.5` from `backend-v2/requirements.txt`.  
**Effort:** 2 minutes. Pair with TD-028.

---

### TD-031 ✅ 🟠 Zero integration tests for FastAPI routes — **FIXED 2026-06-19 (BSA-10)**

**Files:** `backend-v2/conftest.py`, `backend-v2/tests/`  
**Score:** Impact 5 · Risk 5 · Effort 3 → **Priority 30**  
**Fix:** Added 7 in-process tests via `httpx.AsyncClient` over `ASGITransport` (no live server needed): `test_health.py` (2), `test_analyze.py` (5 — CSV upload, response shape, 400 bad extension, 413 oversize, required fields). `test_parity.py` diffs Flask/FastAPI shape and is fenced behind an `integration` marker (excluded from default CI). `pyproject.toml` set `asyncio_mode = "auto"`. **Result:** 7 passed, 0 warnings. This also resolves the remaining half of TD-016.  
**Remaining gap (logged separately):** no test exercises the LLM enricher (TD-033) or the summary endpoint (TD-036).

---

## Priority 2 — Fix Soon

### TD-030 ✅ 🟠 CORS wildcards with `allow_credentials=True` — **FIXED 2026-06-13**

**File:** `backend-v2/app/main.py`  
**Score:** Impact 3 · Risk 4 · Effort 1 → **Priority 35**  
**Description:** `allow_credentials=True` + `allow_methods=["*"]` + `allow_headers=["*"]` violates the CORS spec. When credentials (cookies, auth headers) are involved, browsers reject wildcard `*` for methods and headers. Currently the frontend uses `fetch` without credentials, so this doesn't cause immediate bugs — but it will when auth is added (Sprint-02+).  
**Fix:**

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
```

**Effort:** 5 minutes.

---

### TD-032 ✅ 🟡 `UPLOAD_DIR = Path("uploads")` is process-cwd-relative — **FIXED 2026-06-13**

**File:** `backend-v2/app/routers/analyze.py`  
**Score:** Impact 3 · Risk 3 · Effort 1 → **Priority 30**  
**Description:** `Path("uploads")` resolves relative to wherever `uvicorn` is started, not relative to the `backend-v2/` source tree. Launch from the project root and uploads land in `./uploads/` instead of `backend-v2/uploads/`. This is a silent runtime bug — no error, files just go to the wrong place (or the right place sometimes, depending on how you start the server).  
**Fix:**

```python
UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
```

**Effort:** 2 minutes.

---

### TD-007 ✅ 🟠 `BankStatementAnalyzer` monolith split — FIXED 2026-06-22 (Sprint-05 TD-007/008)

**Fix:** `BankStatementAnalyzer` (~1,280 lines) split into four focused modules: `parsers/excel_parser.py` (466 lines), `parsers/pdf_parser.py` (286 lines), `enrichers/narration_enricher.py` (271 lines), `scorers/confidence_scorer.py` (32 lines). `analyzer.py` is now 299 lines — a thin orchestrator + `TransactionPatternTrainer`. External API unchanged; all existing tests pass without modification.

---

### TD-008 ✅ 🟠 Column-detection duplication addressed — FIXED 2026-06-22 (Sprint-05 TD-007/008)

**Fix:** `find_column()`, `parse_amount()`, `normalize_date()`, `deduplicate_transactions()` extracted to `parsers/excel_parser.py` and imported by `pdf_parser.py`. Remaining coupling is tracked as CR-S5-03 (extract to `parsers/utils.py`).

---

### TD-021 ✅ 🟠 Multi-page PDF: continuation rows silently dropped — **FIXED 2026-06-19**

**Files:** `analyzeModel.py` / `analyzer.py`  
**Score:** Impact 4 · Risk 4 · Effort 3 → **Priority 24**  
**Fix:** Added `_looks_like_header()` staticmethod; `_process_pdf_transactions` now carries `last_known_headers` across tables. Continuation pages (no header in `table[0]`) reuse the last seen header instead of consuming a data row as column names. Logged at DEBUG. Applied to both Flask and FastAPI backends.

---

## Sprint-02 New Debt (opened 2026-06-20)

These were logged against the two new features and the cutover. Source: `docs/code-review.md` (Sprint-02 review).

### TD-033 ⬜ 🔴 LLM enricher double-indexes results onto the wrong transaction

**File:** `backend-v2/app/services/llm_enricher.py` line 106  
**Score:** Impact 5 · Risk 5 · Effort 1 → **Priority 50**  
**Description:** `txn_index = batch_indices[item["index"]]` treats the model-returned **global** index as a **batch offset**. Result is either `IndexError` (swallowed by the catch-all → enrichment silently does nothing) or a category written to the wrong transaction. BSA-04 currently never enriches anything. **Map directly: `txn_index = item["index"]` with a bounds check.** Add a unit test. **Fix before exposing BSA-04 to any user.**  
**Effort:** 30 min code + 30 min test.

### TD-034 ⬜ 🟠 Enrichment runs after aggregates are computed

**Files:** `backend-v2/app/routers/analyze.py`, `analyzer.py`  
**Score:** Impact 4 · Risk 3 · Effort 2 → **Priority 24**  
**Description:** `merchant_insights` and `confidence_summary` are built inside `extract_transactions()` before `enrich_with_llm()` mutates the transactions. LLM-filled merchants/categories never reach the aggregates the frontend charts. Enrich first, then aggregate (or recompute aggregates post-enrichment). Becomes user-visible once TD-033 is fixed.  
**Effort:** 1–2 hours.

### TD-035 ✅ 🟠 LLM enrichment is unbounded and blocks the request — **FIXED 2026-06-20 (Sprint-03)**

**Files:** `backend/app/services/llm_enricher.py`, `analyze.py`  
**Fix:** Refactored `enrich_with_llm()` to run batches concurrently (`asyncio.Semaphore(3)` — 3 in-flight at a time) wrapped in `asyncio.wait_for(enrich_all, timeout=settings.llm_total_timeout_s)`. Added `settings.llm_max_enriched` cap — only the first N uncategorized rows are submitted. Partial results returned on timeout. `ConnectError` and `TimeoutException` still break the batch loop early. Result: bounded latency regardless of statement size.

### TD-036 ⬜ 🟠 Summary endpoint accepts untyped `list[dict]`

**File:** `backend-v2/app/routers/summary.py`  
**Score:** Impact 3 · Risk 3 · Effort 1 → **Priority 30**  
**Description:** `SummaryRequest.transactions: list[dict[str, Any]]` bypasses Pydantic. `amount: "1,200"` → `float()` ValueError → unhandled 500. Reuse the existing `Transaction` schema so validation happens at the boundary. Add a summary unit test on a known fixture.  
**Effort:** 30 min.

### TD-037 ⬜ 🟠 Stale `localhost:5000` strings in frontend after cutover

**Files:** `frontend/App.tsx` line 35, `frontend/services/api.ts` lines 3 + 22  
**Score:** Impact 3 · Risk 2 · Effort 1 → **Priority 20**  
**Description:** Two user-facing error messages and the env fallback still reference port 5000 (deprecated Flask). Post-BSA-09 the app talks to 8000; a backend-down user is pointed at the wrong port, and a missing env var silently targets the soon-to-be-deleted backend. Centralize on `API_BASE` (default 8000) and interpolate it into all error strings.  
**Effort:** 20 min.

### TD-038 ✅ 🟡 BSA-04 / BSA-05 frontend surface — **FIXED 2026-06-21 (Sprint-04 housekeeping)**

**Files:** `frontend/components/TransactionTable.tsx`, `frontend/types.ts`  
**Fix:** Added "Category" column to `TransactionTable.tsx`. When `txn.llm_enriched === true`, an indigo "AI" pill with `title="AI-categorized"` renders next to the category names. Existing regex-categorized rows show categories only. Rows with no category show `—`. The misplaced AI badge that was in the Method column was removed to eliminate duplication.

---

## Sprint-03 New Debt (opened 2026-06-20, from Sprint-03 code review)

### TD-039 ✅ 🟡 `insights` field missing from `AnalysisResult` Pydantic schema — **FIXED 2026-06-21 (Sprint-04 housekeeping)**

**File:** `backend/app/models/schemas.py`  
**Fix:** Added `insights: List[str] = []` to `AnalysisResult`. Swagger UI now documents the field; future `response_model` enforcement won't strip it.

### TD-040 ✅ 🟢 `SummaryResponse` missing `currency` field — **FIXED 2026-06-21 (Sprint-04 housekeeping)**

**File:** `backend/app/models/schemas.py`  
**Fix:** Added `currency: str = "INR"` to `SummaryResponse`. Makes the implicit contract with the frontend explicit; Swagger now documents it.

### TD-041 ✅ 🟢 `backend/` rename complete — **FIXED 2026-06-21 (Sprint-04 housekeeping)**

**Location:** Repository root  
**Fix:** `backend-v2/` renamed to `backend/` on local machine via `git mv`. `.github/workflows/test.yml` already used `backend/`. All remaining stale `backend-v2` references cleaned from `CLAUDE.md` (rename note removed, testing section, arch heading, browser instructions, env var comment).

---

## Priority 3 — Improve When Possible

### TD-016 ✅ Folded into TD-031

**Status:** Resolved. Flask pytest (Sprint-01) + FastAPI httpx suite (BSA-10) together close this. No separate remaining work.

---

### TD-023 ⬜ 🟡 Upload validation trusts extension, not file bytes

**File:** `analyzeController.py` / `analyze.py`  
**Score:** Impact 2 · Risk 3 · Effort 2 → **Priority 20**  
**Description:** A `.exe` renamed to `.pdf` clears the extension whitelist. Low blast radius (parsers fail fast), but verify magic bytes (`%PDF`, `PK\x03\x04`) for defense in depth.  
**Effort:** 1–2 hours.

---

### TD-024 ✅ 🟡 No transaction deduplication — **FIXED 2026-06-21 (BSA-19 + Sprint-04 prompt 03)**

**Files:** `analyzeModel.py` / `analyzer.py`  
**Score:** Impact 3 · Risk 2 · Effort 2 → **Priority 20**  
**Description:** Overlapping table extractions (common in multi-page PDFs) can produce duplicate transactions, inflating totals and merchant insights. Dedupe on `(date, amount, narration, balance)` before scoring.  
**Effort:** 1–2 hours.  
**Fix (two layers):**

- _File-level_ (BSA-19): SHA-256 `file_hash` on `StatementDB` prevents re-parsing the same file.
- _Row-level_ (Sprint-04 prompt 03): `BankStatementAnalyzer._deduplicate_transactions()` — compound key `(date, amount, narration[:100], balance)`, keeps first occurrence, runs after extraction before confidence scoring, in both Excel/CSV and PDF paths. 7 unit tests in `backend/tests/test_dedup.py`.

---

### TD-025 ⬜ 🟡 `transaction_reference` fallback regex grabs any 10+ digit run

**Files:** `analyzeModel.py` / `analyzer.py`  
**Score:** Impact 2 · Risk 2 · Effort 2 → **Priority 20**  
**Description:** The fallback captures beneficiary account or mobile numbers. Require a labeled prefix (RRN/UTR/REF/TXN) or prefer UTR-shaped 12/16-digit candidates.  
**Effort:** 1–2 hours.

---

### TD-026 ⬜ 🟡 Confidence score penalizes balance-less formats unconditionally

**Files:** `analyzeModel.py` / `analyzer.py`  
**Score:** Impact 2 · Risk 1 · Effort 2 → **Priority 15**  
**Description:** `-0.05` for missing `balance` drags down every transaction from formats that legitimately lack a running balance (credit card exports, many CSV formats). Make the penalty conditional on whether the statement format carries balances at all.  
**Effort:** 1 hour.

---

### TD-018 ⬜ 🟡 `TransactionTable` renders all rows with no virtualization

**File:** `frontend/`  
**Score:** Impact 2 · Risk 1 · Effort 3 → **Priority 9**  
**Description:** Statements with 500+ transactions will cause jank. Add `@tanstack/react-virtual` or basic pagination before multi-statement/history features increase row counts.  
**Effort:** 2–3 hours.

---

## Priority 4 — Backlog

### TD-019 ⬜ 🟢 No Dockerfile / docker-compose

**Score:** Impact 2 · Risk 1 · Effort 3 → **Priority 9**  
**Description:** Manual venv + npm setup. Add `backend/Dockerfile` + `docker-compose.yml`. Unblocked now that TD-001 is genuinely fixed.

### TD-001 ✅ 🔴 `requirements.txt` UTF-16 — **RESOLVED 2026-06-20 (BSA-18)**

**File:** `backend-v2/requirements.txt`
**Fix:** Flask (`backend/`) deleted; `backend-v2/requirements.txt` is UTF-8. CI guard added in `.github/workflows/test.yml`:

```bash
file backend-v2/requirements.txt | grep -qE 'ASCII|UTF-8'
```

Regression is now caught on every push.

---

## Prioritized Action Plan

### Sprint-03 — Completed ✅

| ID       | Fix                                                       | Status           |
| -------- | --------------------------------------------------------- | ---------------- |
| TD-033   | LLM enricher index bug + bounds check + unit test         | ✅ Done          |
| TD-037   | Stale `localhost:5000` strings → centralize on `API_BASE` | ✅ Done          |
| TD-036   | Type the summary endpoint input (reuse `Transaction`)     | ✅ Done          |
| TD-034   | Aggregate after enrichment (consistency)                  | ✅ Done          |
| TD-035   | Bound enrichment (Semaphore + wait_for + row cap)         | ✅ Done          |
| TD-001   | CI guard for requirements.txt encoding                    | ✅ Done (BSA-18) |
| CR-S2-08 | Category taxonomy unified (`categories.py`)               | ✅ Done          |

### Sprint-04 — Completed ✅

| ID          | Fix                                                 | Status  |
| ----------- | --------------------------------------------------- | ------- |
| TD-039      | Add `insights` to `AnalysisResult` Pydantic schema  | ✅ Done |
| TD-040      | Add `currency` to `SummaryResponse`                 | ✅ Done |
| TD-041      | Rename `backend-v2/` → `backend/`; clean CLAUDE.md  | ✅ Done |
| TD-038      | AI badge on enriched rows in `TransactionTable.tsx` | ✅ Done |
| BSA-19      | SQLite persistence via SQLModel + Alembic           | ✅ Done |
| TD-024      | Row-level transaction deduplication                 | ✅ Done |
| BSA-13      | CSV / Excel export endpoint                         | ✅ Done |
| BSA-07 lite | Single-statement recurring detection                | ✅ Done |

### Sprint-05 — Completed ✅

| ID          | Fix                                                                 | Status  |
| ----------- | ------------------------------------------------------------------- | ------- |
| CR-S4-01    | Pagination on `GET /api/statements`                                 | ✅ Done |
| CR-S4-02    | `GET /api/statements/{id}/transactions` endpoint                    | ✅ Done |
| CR-S4-03    | CorrectionDB fingerprint comment in `crud.py`                       | ✅ Done |
| CR-S4-05    | Export filename sanitization                                        | ✅ Done |
| BSA-17      | Month-over-month comparison (endpoint + frontend chart)             | ✅ Done |
| BSA-07-full | Cross-statement recurring detection + Alembic migration             | ✅ Done |
| TD-007/008  | Split monolithic analyzer into `parsers/`, `enrichers/`, `scorers/` | ✅ Done |

### Sprint-06 Action Plan

| ID       | Fix                                               | Est.   | Priority          |
| -------- | ------------------------------------------------- | ------ | ----------------- |
| CR-S5-05 | Add query limit in `get_monthly_summary()`        | 30 min | P0 (housekeeping) |
| CR-S5-01 | Add route ordering comment in `statements.py`     | 2 min  | P0 (housekeeping) |
| CR-S5-04 | Staleness comment on `recurring_candidates_json`  | 2 min  | P0 (housekeeping) |
| BSA-06   | Natural-language Q&A over transaction history     | 4–6h   | P0                |
| BSA-20   | Statement history UI (browse + reload from DB)    | 3–4h   | P0                |
| BSA-16   | Category-correction learning loop                 | 3–4h   | P1                |
| TD-023   | Magic-byte upload validation                      | 1–2h   | P1                |
| TD-018   | TransactionTable virtualization                   | 2–3h   | P1                |
| CR-S5-03 | Extract `parsers/utils.py` for shared utilities   | 1–2h   | P2                |
| CR-S5-02 | Surface `top_category` in `MonthlyComparison.tsx` | 30 min | P2                |
| CR-S5-06 | Fix MoM YAxis formatter for sub-₹1k amounts       | 10 min | P2                |
| CR-S5-07 | SubscriptionsCard monthly total caveat            | 15 min | P2                |
| TD-019   | Docker + docker-compose                           | 2–3h   | P2                |

---

## Full Item Table

| ID       | Status | Sev | Area        | Description                                                                          |
| -------- | ------ | --- | ----------- | ------------------------------------------------------------------------------------ |
| TD-001   | ✅     | 🔴  | Backend     | requirements.txt UTF-16 — CI guard added (BSA-18)                                    |
| TD-002   | ✅     | 🔴  | Backend     | Config integration vars defined                                                      |
| TD-003   | ✅     | 🔴  | Backend     | .env.example added                                                                   |
| TD-004   | ✅     | 🔴  | Backend     | Flask debug env-controlled                                                           |
| TD-005   | ✅     | 🔴  | Backend     | Uploaded files cleaned up                                                            |
| TD-006   | ✅     | 🟠  | Backend     | Dead classes removed                                                                 |
| TD-007   | ✅     | 🟠  | Backend     | Monolithic 1,280-line model — split Sprint-05                                        |
| TD-008   | ✅     | 🟠  | Backend     | Column detection duplicated — addressed Sprint-05 (CR-S5-03 tracks remaining work)   |
| TD-009   | ✅     | 🟠  | Backend     | sklearn imports removed                                                              |
| TD-010   | ✅     | 🟠  | Frontend    | API URL via env var                                                                  |
| TD-011   | ✅     | 🟠  | Backend     | File size/ext validation (ext-only)                                                  |
| TD-012   | ✅     | 🟡  | Backend     | logging replaces print                                                               |
| TD-013   | ✅     | 🟡  | Backend     | Double assignment fixed                                                              |
| TD-014   | ✅     | 🟡  | Backend     | Dead vars removed                                                                    |
| TD-015   | ✅     | 🟡  | Backend     | PDF confidence_score added                                                           |
| TD-016   | ✅     | 🟠  | Testing     | Folded into TD-031 (Flask + FastAPI suites both exist)                               |
| TD-017   | ✅     | 🟡  | Backend     | CORS default tightened (Flask)                                                       |
| TD-018   | ⬜     | 🟡  | Frontend    | Table renders all rows                                                               |
| TD-019   | ⬜     | 🟢  | Infra       | No Docker                                                                            |
| TD-020   | ✅     | 🟢  | Repo        | .gitIgnore → .gitignore                                                              |
| TD-021   | ✅     | 🟠  | Backend     | Multi-page PDF rows dropped                                                          |
| TD-022   | ✅     | 🟠  | Backend     | Dead Pennyless fn deleted (Flask)                                                    |
| TD-023   | ⬜     | 🟡  | Backend     | Validation trusts extension not bytes                                                |
| TD-024   | ✅     | 🟡  | Backend     | No transaction deduplication — file-level (BSA-19) + row-level (Sprint-04 prompt 03) |
| TD-025   | ⬜     | 🟡  | Backend     | txn_reference regex over-greedy                                                      |
| TD-026   | ⬜     | 🟡  | Backend     | Confidence penalizes balance-less formats                                            |
| TD-027   | ✅     | 🟡  | Backend     | /api/health added to Flask                                                           |
| TD-028   | ✅     | 🔴  | FastAPI     | reload=True hardcoded in run.py                                                      |
| TD-029   | ✅     | 🔴  | FastAPI     | Dead `import requests` + dep in requirements                                         |
| TD-030   | ✅     | 🟠  | FastAPI     | CORS wildcards with allow_credentials=True                                           |
| TD-031   | ✅     | 🟠  | FastAPI     | FastAPI integration tests added (BSA-10)                                             |
| TD-032   | ✅     | 🟡  | FastAPI     | UPLOAD_DIR is cwd-relative, not file-relative                                        |
| TD-033   | ✅     | 🔴  | FastAPI/LLM | Enricher double-indexes results onto wrong txn — fixed Sprint-03                     |
| TD-034   | ✅     | 🟠  | FastAPI/LLM | Enrichment runs after aggregates computed — fixed Sprint-03                          |
| TD-035   | ✅     | 🟠  | FastAPI/LLM | Enrichment bounded — Semaphore + wait_for + cap — fixed Sprint-03                    |
| TD-036   | ✅     | 🟠  | FastAPI     | Summary endpoint accepts untyped list[dict] — fixed Sprint-03                        |
| TD-037   | ✅     | 🟠  | Frontend    | Stale localhost:5000 strings after cutover — fixed Sprint-03                         |
| TD-038   | ✅     | 🟡  | Frontend    | Category column + AI badge on LLM-enriched rows — done Sprint-04                     |
| TD-039   | ✅     | 🟡  | FastAPI     | `insights` added to AnalysisResult Pydantic schema — done Sprint-04                  |
| TD-040   | ✅     | 🟢  | FastAPI     | `currency: str = "INR"` added to SummaryResponse — done Sprint-04                    |
| TD-041   | ✅     | 🟢  | Repo        | backend-v2 → backend rename complete + CLAUDE.md cleaned Sprint-04                   |
| CR-S5-01 | ⬜     | 🟡  | Backend     | Route ordering fragile in statements.py — needs comment                              |
| CR-S5-02 | ⬜     | 🟢  | Frontend    | top_category not rendered in MonthlyComparison.tsx                                   |
| CR-S5-03 | ⬜     | 🟢  | Backend     | pdf_parser imports shared utils from excel_parser — extract parsers/utils.py         |
| CR-S5-04 | ⬜     | 🟢  | Backend     | recurring_candidates_json staleness not documented in crud.py                        |
| CR-S5-05 | ⬜     | 🟠  | Backend     | get_monthly_summary() loads all transactions without a cap                           |
| CR-S5-06 | ⬜     | 🟢  | Frontend    | MoM YAxis formatter breaks on sub-₹1k amounts                                        |
| CR-S5-07 | ⬜     | 🟢  | Frontend    | SubscriptionsCard monthly total assumes all subscriptions are monthly                |

---

_Code review: `docs/code-review.md` · Sprint plan: `docs/sprint-01-plan.md` · Architecture: `docs/architecture.md`_
