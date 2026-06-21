# Technical Debt Report — Bank Statement Analyzer

**Original:** 2026-05-29 · **Updated:** 2026-06-21 (post-BSA-07 lite recurring detection)
**Reviewed by:** Claude (Cowork)
**Project:** Bank Statement Analyzer (FastAPI/React/TypeScript)

Severity scale: 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low  
Status: ✅ Resolved · ⚠️ Reopened · ⬜ Open

---

## Status Snapshot (post-BSA-19 — Sprint-04)

| Resolved ✅                                                               | Open ⬜                                           |
| ------------------------------------------------------------------------- | ------------------------------------------------- |
| TD-001–006, 009–015, 017, 020, 021, 022, 024, 027–041; CR-S3-01, CR-S3-05 | TD-007, 008, 018, 019, 023, 025, 026; BSA-07-full |

**34 resolved, 7 open, TD-016 folded into TD-031 (resolved). CR-S3-01 and CR-S3-05 resolved via BSA-07 lite.**

> BSA-19 (Sprint-04) closed TD-024 at file level (SHA-256 `file_hash` on `StatementDB`). Sprint-04 prompt 03 added row-level dedup inside the parser (`_deduplicate_transactions` on compound key `date+amount+narration+balance`).  
> Sprint-04 housekeeping (first commit) closed four items: TD-039 (`insights` field added to `AnalysisResult`), TD-040 (`currency` field added to `SummaryResponse`), TD-041 (`backend-v2/` renamed to `backend/` on disk; stale references cleaned from CLAUDE.md), and TD-038 (Category column with AI badge added to `TransactionTable.tsx` — `title="AI-categorized"` for accessibility).  
> **BSA-13 ✅ (2026-06-21):** CSV/Excel export shipped — `POST /api/export/transactions`, `exportTransactions()` in `api.ts`, "↓ CSV" + "↓ Excel" buttons in `TransactionTable`.  
> **BSA-07 lite ✅ (2026-06-21):** Recurring detection MVP — `detect_recurring()` + `recurring_candidates` in schema + ↻ pill in merchant table. CV threshold raised to 0.25 (CR-S3-01 ✅). Four `detect_recurring` tests added (CR-S3-05 ✅). Full cross-statement recurring (BSA-07-full) deferred to Sprint-05.

---

## BSA-07-full ⬜ 🟡 Cross-statement recurring detection requires persistence

**Ticket:** BSA-07-full (deferred from BSA-07 lite, Sprint-04)  
**Score:** Impact 4 · Risk 2 · Effort 4 → **Priority 20**  
**Description:** `detect_recurring()` (BSA-07 lite) detects recurring merchants within a single statement. True recurring detection — confirming that the same subscription or charge appears across multiple uploaded statements for the same account — requires comparing `recurring_candidates` across `StatementDB` rows. The `StatementDB` persistence layer (BSA-19) is now in place, so the data is available; this is purely a query + aggregation gap.  
**Fix:** Sprint-05 — aggregate `recurring_candidates` JSON across `StatementDB` rows matching the same `account_number`, group by merchant, and surface cross-statement recurring with confidence scores based on inter-statement frequency.  
**Effort:** 1–2 days (new CRUD query + API field + UI).

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

### TD-007 ⬜ 🟠 `BankStatementAnalyzer` is one ~1,280-line class

**Files:** `backend/app/models/analyzeModel.py`, `backend-v2/app/models/analyzer.py`  
**Score:** Impact 4 · Risk 4 · Effort 5 → **Priority 8**  
**Description:** File-type routing, Excel/CSV parsing, PDF parsing, date normalization, narration enrichment, metadata extraction, confidence scoring, and merchant aggregation all live in one class. Can't unit-test any component in isolation. Split target: `parsers/excel_parser.py`, `parsers/pdf_parser.py`, `enrichers/narration_enricher.py`, `scorers/confidence_scorer.py`. Best deferred to BSA-09 (Flask cutover) — at that point there's one canonical copy.  
**Effort:** 4–6 hours. Deferred to Sprint-02/03.

---

### TD-008 ⬜ 🟠 Column-detection logic duplicated between Excel and PDF paths

**Files:** `analyzeModel.py` / `analyzer.py`  
**Score:** Impact 3 · Risk 3 · Effort 2 → **Priority 24**  
**Description:** Identical `find_column([...])` sequences and the credit/debit/amount → `(amount, type)` resolution appear independently in `_process_excel_csv()` and `_process_pdf_transactions()`. Extract `_detect_columns(df) -> ColumnMap` and `_resolve_amount(row, cols)`. Removes ~80 lines and eliminates a drift risk. Do alongside TD-007.

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

### Sprint-04 Housekeeping (first commit) — Completed ✅

| ID     | Fix                                                 | Status  |
| ------ | --------------------------------------------------- | ------- |
| TD-039 | Add `insights` to `AnalysisResult` Pydantic schema  | ✅ Done |
| TD-040 | Add `currency` to `SummaryResponse`                 | ✅ Done |
| TD-041 | Rename `backend-v2/` → `backend/`; clean CLAUDE.md  | ✅ Done |
| TD-038 | AI badge on enriched rows in `TransactionTable.tsx` | ✅ Done |

### Sprint-04 P0 (remaining)

| ID     | Fix                                                 | Est. |
| ------ | --------------------------------------------------- | ---- |
| TD-024 | Transaction deduplication (higher risk post-TD-021) | 1–2h |
| TD-023 | Magic-byte upload validation                        | 1–2h |

### Sprint-04/05 (architectural)

| ID     | Fix                             | Est.               |
| ------ | ------------------------------- | ------------------ |
| TD-007 | Split monolithic analyzer       | 4–6h               |
| TD-008 | Extract shared column detection | paired with TD-007 |
| TD-019 | Docker + compose                | 2h                 |
| TD-018 | TransactionTable virtualization | 2–3h               |

---

## Full Item Table

| ID     | Status | Sev | Area        | Description                                                                          |
| ------ | ------ | --- | ----------- | ------------------------------------------------------------------------------------ |
| TD-001 | ✅     | 🔴  | Backend     | requirements.txt UTF-16 — CI guard added (BSA-18)                                    |
| TD-002 | ✅     | 🔴  | Backend     | Config integration vars defined                                                      |
| TD-003 | ✅     | 🔴  | Backend     | .env.example added                                                                   |
| TD-004 | ✅     | 🔴  | Backend     | Flask debug env-controlled                                                           |
| TD-005 | ✅     | 🔴  | Backend     | Uploaded files cleaned up                                                            |
| TD-006 | ✅     | 🟠  | Backend     | Dead classes removed                                                                 |
| TD-007 | ⬜     | 🟠  | Backend     | Monolithic 1,280-line model                                                          |
| TD-008 | ⬜     | 🟠  | Backend     | Column detection duplicated                                                          |
| TD-009 | ✅     | 🟠  | Backend     | sklearn imports removed                                                              |
| TD-010 | ✅     | 🟠  | Frontend    | API URL via env var                                                                  |
| TD-011 | ✅     | 🟠  | Backend     | File size/ext validation (ext-only)                                                  |
| TD-012 | ✅     | 🟡  | Backend     | logging replaces print                                                               |
| TD-013 | ✅     | 🟡  | Backend     | Double assignment fixed                                                              |
| TD-014 | ✅     | 🟡  | Backend     | Dead vars removed                                                                    |
| TD-015 | ✅     | 🟡  | Backend     | PDF confidence_score added                                                           |
| TD-016 | ✅     | 🟠  | Testing     | Folded into TD-031 (Flask + FastAPI suites both exist)                               |
| TD-017 | ✅     | 🟡  | Backend     | CORS default tightened (Flask)                                                       |
| TD-018 | ⬜     | 🟡  | Frontend    | Table renders all rows                                                               |
| TD-019 | ⬜     | 🟢  | Infra       | No Docker                                                                            |
| TD-020 | ✅     | 🟢  | Repo        | .gitIgnore → .gitignore                                                              |
| TD-021 | ✅     | 🟠  | Backend     | Multi-page PDF rows dropped                                                          |
| TD-022 | ✅     | 🟠  | Backend     | Dead Pennyless fn deleted (Flask)                                                    |
| TD-023 | ⬜     | 🟡  | Backend     | Validation trusts extension not bytes                                                |
| TD-024 | ✅     | 🟡  | Backend     | No transaction deduplication — file-level (BSA-19) + row-level (Sprint-04 prompt 03) |
| TD-025 | ⬜     | 🟡  | Backend     | txn_reference regex over-greedy                                                      |
| TD-026 | ⬜     | 🟡  | Backend     | Confidence penalizes balance-less formats                                            |
| TD-027 | ✅     | 🟡  | Backend     | /api/health added to Flask                                                           |
| TD-028 | ✅     | 🔴  | FastAPI     | reload=True hardcoded in run.py                                                      |
| TD-029 | ✅     | 🔴  | FastAPI     | Dead `import requests` + dep in requirements                                         |
| TD-030 | ✅     | 🟠  | FastAPI     | CORS wildcards with allow_credentials=True                                           |
| TD-031 | ✅     | 🟠  | FastAPI     | FastAPI integration tests added (BSA-10)                                             |
| TD-032 | ✅     | 🟡  | FastAPI     | UPLOAD_DIR is cwd-relative, not file-relative                                        |
| TD-033 | ✅     | 🔴  | FastAPI/LLM | Enricher double-indexes results onto wrong txn — fixed Sprint-03                     |
| TD-034 | ✅     | 🟠  | FastAPI/LLM | Enrichment runs after aggregates computed — fixed Sprint-03                          |
| TD-035 | ✅     | 🟠  | FastAPI/LLM | Enrichment bounded — Semaphore + wait_for + cap — fixed Sprint-03                    |
| TD-036 | ✅     | 🟠  | FastAPI     | Summary endpoint accepts untyped list[dict] — fixed Sprint-03                        |
| TD-037 | ✅     | 🟠  | Frontend    | Stale localhost:5000 strings after cutover — fixed Sprint-03                         |
| TD-038 | ✅     | 🟡  | Frontend    | Category column + AI badge on LLM-enriched rows — done Sprint-04                     |
| TD-039 | ✅     | 🟡  | FastAPI     | `insights` added to AnalysisResult Pydantic schema — done Sprint-04                  |
| TD-040 | ✅     | 🟢  | FastAPI     | `currency: str = "INR"` added to SummaryResponse — done Sprint-04                    |
| TD-041 | ✅     | 🟢  | Repo        | backend-v2 → backend rename complete + CLAUDE.md cleaned Sprint-04                   |

---

_Code review: `docs/code-review.md` · Sprint plan: `docs/sprint-01-plan.md` · Architecture: `docs/architecture.md`_
