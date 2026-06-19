# Technical Debt Report — Bank Statement Analyzer

**Original:** 2026-05-29 · **Updated:** 2026-06-13  
**Reviewed by:** Claude (Cowork)  
**Project:** Bank Statement Analyzer (Flask + FastAPI/React/TypeScript)

Severity scale: 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low  
Status: ✅ Resolved · ⚠️ Reopened · ⬜ Open

---

## Status Snapshot (post-Sprint-01)

| Resolved ✅ | Open ⬜ | Reopened ⚠️ |
|------------|---------|-------------|
| TD-002–006, 009–015, 017, 020, 021, 022, 027 | TD-007, 008, 018, 019, 023–026, 028–032 | TD-001, TD-016 |

**15 resolved, 14 open (5 carried + 5 FastAPI-new), 2 tracked special**

> TD-001 was re-encoded this sprint (again). TD-016 was partially resolved — pytest exists for Flask only; FastAPI tests logged as TD-031.

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

### TD-031 ⬜ 🟠 Zero integration tests for FastAPI routes
**Files:** `backend-v2/` (no `tests/` directory)  
**Score:** Impact 5 · Risk 5 · Effort 3 → **Priority 30**  
**Description:** The pytest suite in `backend/tests/` covers Flask only. FastAPI's `/api/health` and `/api/analyze/bank/statement` have no tests. This means: (1) BSA-09 (Flask cutover) has no parity baseline — we can't prove the two backends return the same shape; (2) any regression in the FastAPI route (response model mismatch, CORS breakage, auth middleware in future) goes undetected.  
**What's needed:**
- `backend-v2/tests/test_health.py` — GET `/api/health` returns 200 + correct JSON
- `backend-v2/tests/test_analyze.py` — POST with fixture CSV + PDF; assert response shape matches `AnalyzeResponse`; assert 400 on bad extension; assert 413 on oversized file
- `backend-v2/tests/test_parity.py` — send same file to both Flask (port 5000) and FastAPI (port 8000), diff JSON shape (not values)
- Tool: `httpx.AsyncClient` with `pytest-asyncio`  
**Effort:** 3–4 hours.

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

## Priority 3 — Improve When Possible

### TD-016 ⚠️ pytest exists for Flask only — FastAPI coverage is zero
**Status:** Partially resolved (Flask pytest added TD-016 in Sprint-01). FastAPI coverage tracked as TD-031 above.  
**Remaining:** Add `backend-v2/tests/` with httpx-based async tests.

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

### TD-001 ⚠️ 🔴 `requirements.txt` UTF-16 — WATCH
**File:** `backend/requirements.txt`  
**Status:** Fixed twice (2026-05-29, 2026-05-31). Add a CI guard so it can't regress:
```bash
# In CI / pre-commit hook:
file backend/requirements.txt | grep -qE 'ASCII|UTF-8' || (echo "requirements.txt is not UTF-8!" && exit 1)
```
This item stays in the backlog until that guard exists.

---

## Prioritized Action Plan

### Sprint-02 P0 (fix in first 2 hours)

| ID | Fix | Est. |
|----|-----|------|
| TD-028 | `reload=True` → env-controlled | 5 min |
| TD-029 | Delete `import requests` + dep | 5 min |
| TD-030 | CORS wildcards → explicit lists | 5 min |
| TD-032 | `UPLOAD_DIR` → file-relative path | 5 min |

These four are all 1-liner fixes that belong in a single "FastAPI housekeeping" commit.

### Sprint-02 P1 (functional value)

| ID | Fix | Est. |
|----|-----|------|
| TD-031 | FastAPI integration tests (httpx) | 3–4h |
| TD-024 | Transaction deduplication | 1–2h |

### Sprint-02/03 (architectural)

| ID | Fix | Est. |
|----|-----|------|
| TD-007 | Split monolithic analyzer | 4–6h |
| TD-008 | Extract shared column detection | paired with TD-007 |
| TD-019 | Docker + compose | 2h |
| TD-023 | Magic-byte upload validation | 1–2h |

---

## Full Item Table

| ID | Status | Sev | Area | Description |
|----|--------|-----|------|-------------|
| TD-001 | ⚠️ Watch | 🔴 | Backend | requirements.txt UTF-16 — add CI guard |
| TD-002 | ✅ | 🔴 | Backend | Config integration vars defined |
| TD-003 | ✅ | 🔴 | Backend | .env.example added |
| TD-004 | ✅ | 🔴 | Backend | Flask debug env-controlled |
| TD-005 | ✅ | 🔴 | Backend | Uploaded files cleaned up |
| TD-006 | ✅ | 🟠 | Backend | Dead classes removed |
| TD-007 | ⬜ | 🟠 | Backend | Monolithic 1,280-line model |
| TD-008 | ⬜ | 🟠 | Backend | Column detection duplicated |
| TD-009 | ✅ | 🟠 | Backend | sklearn imports removed |
| TD-010 | ✅ | 🟠 | Frontend | API URL via env var |
| TD-011 | ✅ | 🟠 | Backend | File size/ext validation (ext-only) |
| TD-012 | ✅ | 🟡 | Backend | logging replaces print |
| TD-013 | ✅ | 🟡 | Backend | Double assignment fixed |
| TD-014 | ✅ | 🟡 | Backend | Dead vars removed |
| TD-015 | ✅ | 🟡 | Backend | PDF confidence_score added |
| TD-016 | ⚠️ Partial | 🟠 | Testing | Flask pytest done; FastAPI tests → TD-031 |
| TD-017 | ✅ | 🟡 | Backend | CORS default tightened (Flask) |
| TD-018 | ⬜ | 🟡 | Frontend | Table renders all rows |
| TD-019 | ⬜ | 🟢 | Infra | No Docker |
| TD-020 | ✅ | 🟢 | Repo | .gitIgnore → .gitignore |
| TD-021 | ✅ | 🟠 | Backend | Multi-page PDF rows dropped |
| TD-022 | ✅ | 🟠 | Backend | Dead Pennyless fn deleted (Flask) |
| TD-023 | ⬜ | 🟡 | Backend | Validation trusts extension not bytes |
| TD-024 | ⬜ | 🟡 | Backend | No transaction deduplication |
| TD-025 | ⬜ | 🟡 | Backend | txn_reference regex over-greedy |
| TD-026 | ⬜ | 🟡 | Backend | Confidence penalizes balance-less formats |
| TD-027 | ✅ | 🟡 | Backend | /api/health added to Flask |
| TD-028 | ✅ | 🔴 | FastAPI | reload=True hardcoded in run.py |
| TD-029 | ✅ | 🔴 | FastAPI | Dead `import requests` + dep in requirements |
| TD-030 | ✅ | 🟠 | FastAPI | CORS wildcards with allow_credentials=True |
| TD-031 | ⬜ | 🟠 | FastAPI | Zero integration tests for FastAPI routes |
| TD-032 | ✅ | 🟡 | FastAPI | UPLOAD_DIR is cwd-relative, not file-relative |

---

*Code review: `docs/code-review.md` · Sprint plan: `docs/sprint-01-plan.md` · Architecture: `docs/architecture.md`*
