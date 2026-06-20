# Technical Debt Report — Bank Statement Analyzer

**Original:** 2026-05-29 · **Updated:** 2026-06-20 (post-Sprint-03, full close-out)
**Reviewed by:** Claude (Cowork)
**Project:** Bank Statement Analyzer (FastAPI/React/TypeScript)

Severity scale: 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low  
Status: ✅ Resolved · ⚠️ Reopened · ⬜ Open

---

## Status Snapshot (post-Sprint-03 full close-out)

| Resolved ✅                                      | Open ⬜                             |
| ------------------------------------------------ | ----------------------------------- |
| TD-001–006, 009–015, 017, 020, 021, 022, 027–037 | TD-007, 008, 018, 019, 023–026, 038 |

**29 resolved, 8 open, TD-016 folded into TD-031 (resolved)**

> Sprint-03 full close-out resolved all fast-follow fixes (TD-033/034/035/036/037), deleted Flask (BSA-18 — closes TD-001 CI guard), and unified the category taxonomy (CR-S2-08). TD-038 is now **partially resolved** — the Spending Summary card (BSA-12) is wired; the AI badge on transaction rows still remains. TD-035 (bounded enrichment) is **resolved** — `asyncio.wait_for` + `Semaphore(3)` + row cap are in production. Three new observations from Sprint-03 code review: CR-S3-02 (schema drift on `insights` field), CR-S3-03 (`SummaryResponse` missing `currency`), CR-S3-04 (AI badge still missing). Added below as new debt items.

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

### TD-038 ⚠️ 🟡 BSA-04 / BSA-05 frontend surface — PARTIAL (Spending Summary done; AI badge open)

**Files:** `frontend/components/TransactionTable.tsx`, `frontend/types.ts`  
**Score (remaining):** Impact 2 · Risk 1 · Effort 1 → **Priority 8**  
**Sprint-03 progress:** `SpendingSummary.tsx` is wired and calls `POST /summary` (BSA-12 ✅). `llm_enriched?: boolean` is in `types.ts`. `InsightsStrip.tsx` renders insight callouts.  
**Remaining:** `TransactionTable.tsx` does not render any visual indicator on LLM-enriched rows. Users can't distinguish AI-assigned from regex-assigned categories. Add a subtle "AI" pill or icon in the category cell when `txn.llm_enriched === true`.  
**Effort:** ~30 min.

---

## Sprint-03 New Debt (opened 2026-06-20, from Sprint-03 code review)

### TD-039 ⬜ 🟡 `insights` field missing from `AnalysisResult` Pydantic schema

**File:** `backend/app/models/schemas.py`  
**Score:** Impact 2 · Risk 2 · Effort 1 → **Priority 20**  
**Description:** `AnalysisResult` in `schemas.py` does not include an `insights: list[str]` field. The field is injected at the dict level in `analyze.py` and passes through because the route doesn't use a strict `response_model`. `frontend/types.ts` correctly types it. Swagger UI won't document it; any future response-model enforcement will strip it silently.  
**Fix:** Add `insights: list[str] = []` to `AnalysisResult` in `schemas.py`. One line.  
**Effort:** 5 minutes.

### TD-040 ⬜ 🟢 `SummaryResponse` missing `currency` field

**File:** `backend/app/models/schemas.py`, `frontend/components/SpendingSummary.tsx`  
**Score:** Impact 1 · Risk 1 · Effort 1 → **Priority 10**  
**Description:** `SpendingSummary.tsx` reads `summary.currency ?? "INR"` as a fallback. The backend doesn't emit a `currency` field — the `??` implies a multi-currency intent the backend doesn't fulfil. Fine for now (single-market tool), but creates a contract gap. Add `currency: str = "INR"` to `SummaryResponse` to make the implicit explicit.  
**Effort:** 5 minutes. Do alongside TD-039.

### TD-041 ⬜ 🟢 `backend/` rename still pending (empty dir conflict on mounted FS)

**Location:** Repository root  
**Score:** Impact 1 · Risk 1 · Effort 0 → **Priority 5** (user action, not code)  
**Description:** An empty `backend/` directory was created during the Sprint-03 close-out session (failed `mkdir -p` in the sandbox). `backend-v2/` still exists and is canonical. Run the following on your local machine to complete the rename:

```bash
rmdir backend          # remove the empty placeholder
git mv backend-v2 backend
git commit -m "BSA-20: rename backend-v2 to backend"
```

Update `.github/workflows/test.yml` references at the same time (already reflected in current docs).

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

### TD-024 ⬜ 🟡 No transaction deduplication

**Files:** `analyzeModel.py` / `analyzer.py`  
**Score:** Impact 3 · Risk 2 · Effort 2 → **Priority 20**  
**Description:** Overlapping table extractions (common in multi-page PDFs) can produce duplicate transactions, inflating totals and merchant insights. Dedupe on `(date, amount, narration, balance)` before scoring.  
**Effort:** 1–2 hours.

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
**Description:** Manual venv + npm setup. Add `backend-v2/Dockerfile` + `docker-compose.yml`. Unblocked now that TD-001 is genuinely fixed.

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

### Sprint-04 P0 (carry-forward + value)

| ID     | Fix                                                     | Est.  |
| ------ | ------------------------------------------------------- | ----- |
| TD-039 | Add `insights` to `AnalysisResult` Pydantic schema      | 5 min |
| TD-040 | Add `currency` to `SummaryResponse`                     | 5 min |
| TD-041 | Rename `backend-v2/` → `backend/` (git mv, user action) | 5 min |
| TD-038 | AI badge on enriched rows in `TransactionTable.tsx`     | 30min |
| TD-024 | Transaction deduplication (higher risk post-TD-021)     | 1–2h  |
| TD-023 | Magic-byte upload validation                            | 1–2h  |

### Sprint-04/05 (architectural)

| ID     | Fix                             | Est.               |
| ------ | ------------------------------- | ------------------ |
| TD-007 | Split monolithic analyzer       | 4–6h               |
| TD-008 | Extract shared column detection | paired with TD-007 |
| TD-019 | Docker + compose                | 2h                 |
| TD-018 | TransactionTable virtualization | 2–3h               |

---

## Full Item Table

| ID     | Status | Sev | Area        | Description                                                       |
| ------ | ------ | --- | ----------- | ----------------------------------------------------------------- |
| TD-001 | ✅     | 🔴  | Backend     | requirements.txt UTF-16 — CI guard added (BSA-18)                 |
| TD-002 | ✅     | 🔴  | Backend     | Config integration vars defined                                   |
| TD-003 | ✅     | 🔴  | Backend     | .env.example added                                                |
| TD-004 | ✅     | 🔴  | Backend     | Flask debug env-controlled                                        |
| TD-005 | ✅     | 🔴  | Backend     | Uploaded files cleaned up                                         |
| TD-006 | ✅     | 🟠  | Backend     | Dead classes removed                                              |
| TD-007 | ⬜     | 🟠  | Backend     | Monolithic 1,280-line model                                       |
| TD-008 | ⬜     | 🟠  | Backend     | Column detection duplicated                                       |
| TD-009 | ✅     | 🟠  | Backend     | sklearn imports removed                                           |
| TD-010 | ✅     | 🟠  | Frontend    | API URL via env var                                               |
| TD-011 | ✅     | 🟠  | Backend     | File size/ext validation (ext-only)                               |
| TD-012 | ✅     | 🟡  | Backend     | logging replaces print                                            |
| TD-013 | ✅     | 🟡  | Backend     | Double assignment fixed                                           |
| TD-014 | ✅     | 🟡  | Backend     | Dead vars removed                                                 |
| TD-015 | ✅     | 🟡  | Backend     | PDF confidence_score added                                        |
| TD-016 | ✅     | 🟠  | Testing     | Folded into TD-031 (Flask + FastAPI suites both exist)            |
| TD-017 | ✅     | 🟡  | Backend     | CORS default tightened (Flask)                                    |
| TD-018 | ⬜     | 🟡  | Frontend    | Table renders all rows                                            |
| TD-019 | ⬜     | 🟢  | Infra       | No Docker                                                         |
| TD-020 | ✅     | 🟢  | Repo        | .gitIgnore → .gitignore                                           |
| TD-021 | ✅     | 🟠  | Backend     | Multi-page PDF rows dropped                                       |
| TD-022 | ✅     | 🟠  | Backend     | Dead Pennyless fn deleted (Flask)                                 |
| TD-023 | ⬜     | 🟡  | Backend     | Validation trusts extension not bytes                             |
| TD-024 | ⬜     | 🟡  | Backend     | No transaction deduplication                                      |
| TD-025 | ⬜     | 🟡  | Backend     | txn_reference regex over-greedy                                   |
| TD-026 | ⬜     | 🟡  | Backend     | Confidence penalizes balance-less formats                         |
| TD-027 | ✅     | 🟡  | Backend     | /api/health added to Flask                                        |
| TD-028 | ✅     | 🔴  | FastAPI     | reload=True hardcoded in run.py                                   |
| TD-029 | ✅     | 🔴  | FastAPI     | Dead `import requests` + dep in requirements                      |
| TD-030 | ✅     | 🟠  | FastAPI     | CORS wildcards with allow_credentials=True                        |
| TD-031 | ✅     | 🟠  | FastAPI     | FastAPI integration tests added (BSA-10)                          |
| TD-032 | ✅     | 🟡  | FastAPI     | UPLOAD_DIR is cwd-relative, not file-relative                     |
| TD-033 | ✅     | 🔴  | FastAPI/LLM | Enricher double-indexes results onto wrong txn — fixed Sprint-03  |
| TD-034 | ✅     | 🟠  | FastAPI/LLM | Enrichment runs after aggregates computed — fixed Sprint-03       |
| TD-035 | ✅     | 🟠  | FastAPI/LLM | Enrichment bounded — Semaphore + wait_for + cap — fixed Sprint-03 |
| TD-036 | ✅     | 🟠  | FastAPI     | Summary endpoint accepts untyped list[dict] — fixed Sprint-03     |
| TD-037 | ✅     | 🟠  | Frontend    | Stale localhost:5000 strings after cutover — fixed Sprint-03      |
| TD-038 | ⚠️     | 🟡  | Frontend    | BSA-04/05 UI — summary card done; AI badge on rows still open     |
| TD-039 | ⬜     | 🟡  | FastAPI     | `insights` missing from AnalysisResult Pydantic schema            |
| TD-040 | ⬜     | 🟢  | FastAPI     | SummaryResponse missing `currency` field                          |
| TD-041 | ⬜     | 🟢  | Repo        | backend-v2 → backend rename (user action, git mv)                 |

---

_Code review: `docs/code-review.md` · Sprint plan: `docs/sprint-01-plan.md` · Architecture: `docs/architecture.md`_
