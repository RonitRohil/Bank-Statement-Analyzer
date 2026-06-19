# Changelog — Bank Statement Analyzer

All notable changes to this project are documented here.  
Format: `[Date] — [Type] — [Short description]`

---

## 2026-06-19 — BSA-05: Add POST /api/analyze/bank/summary endpoint

**Type:** Feature (financial summary)
**Change:** New stateless endpoint that accepts the transactions array returned by `/api/analyze/bank/statement` and computes a financial summary — no I/O, no LLM, no state.

- `backend-v2/app/routers/summary.py` (new): `summarize_transactions()` — sync `def` (pure CPU math); computes income/expense totals, net, per-category spend breakdown with percentage-of-total, top 10 merchants by spend, transaction count, average transaction amount, and optional date range.
- `backend-v2/app/models/schemas.py`: added `CategoryBreakdown`, `TopMerchant`, `SummaryResponse` Pydantic models.
- `backend-v2/app/main.py`: imports and registers `summary.router`.

**Design notes:**
- Category totals are counted once per category per transaction (a multi-category transaction contributes full spend to each category). This means category percentages can sum to >100% — intentional; see prompt BSA-05 constraints.
- Merchant breakdown covers expense (debit) transactions only; credits are excluded from category/merchant tallies.
- `date_range` is derived from `transaction_date` strings via lexicographic sort (ISO YYYY-MM-DD format assumed from the analyze endpoint output).
- Endpoint is `def` not `async def` — no I/O, so `asyncio.to_thread` would add overhead with no benefit.

**Files affected:** backend-v2/app/routers/summary.py (new), backend-v2/app/models/schemas.py, backend-v2/app/main.py

---

## 2026-06-19 — BSA-04: LLM categorization fallback via Ollama

**Type:** Feature (AI enrichment)
**Change:** Transactions where regex analysis returns `category=[]` are now enriched by a local Ollama model in async batches of 10. Uses `httpx.AsyncClient` against Ollama's OpenAI-compatible endpoint (`/v1/chat/completions`) — no new dependencies needed since `httpx` is already in requirements. LLM failure (Ollama not running, bad JSON, HTTP error) is fully caught and logged — the endpoint still returns results unchanged.

**Provider decision:** Prompt (BSA-04) originally specified Claude Haiku (Anthropic). Switched to Ollama (`qwen2.5:7b`) for local development — Anthropic API is paid; Ollama is free and already in use in the FinanceAssistant project. Can be swapped back for production by changing the Ollama endpoint to a hosted model.

- `backend-v2/app/services/llm_enricher.py` (new): `enrich_with_llm()` async function; builds batches, POSTs to Ollama, maps results back by index. `ConnectError` breaks the loop early (no point retrying batches if Ollama is down). Adds `llm_enriched=True` flag on enriched transactions. Logs prompt+completion token counts at DEBUG level.
- `backend-v2/app/routers/analyze.py`: imports and calls `enrich_with_llm()` after `extract_transactions()` succeeds; runs only when transactions list is non-empty.
- `backend-v2/app/config/settings.py`: added `ollama_base_url: str = "http://localhost:11434"` and `ollama_model: str = "qwen2.5:7b"` — matches FinanceAssistant defaults.
- `backend-v2/app/models/schemas.py`: added `llm_enriched: bool = False` to `Transaction` — `True` when LLM filled the category.
- `backend-v2/.env.example`: rewrote with all supported vars documented; added Ollama settings.
- `backend-v2/app/services/__init__.py` (new): empty package init for the services module.

**Constraints respected:**
- LLM never called per-transaction; always batched (10/call).
- Ollama not running → `ConnectError` caught, enrichment skipped, endpoint unaffected.
- No new pip dependency — `httpx` already in requirements for test suite.

**Files affected:** backend-v2/app/services/llm_enricher.py (new), backend-v2/app/services/__init__.py (new), backend-v2/app/routers/analyze.py, backend-v2/app/config/settings.py, backend-v2/app/models/schemas.py, backend-v2/.env.example

---

## 2026-06-19 — BSA-09: Cut frontend over to FastAPI on port 8000; deprecate Flask

**Type:** Feature (cutover)
**Change:** Frontend now points exclusively to FastAPI (port 8000). Flask backend (port 5000) deprecated but preserved for one sprint as a rollback option.

- `frontend/.env.local`: `VITE_API_URL=http://localhost:8000` (created — gitignored, local-only)
- `frontend/.env.example`: updated to show port 8000 with Sprint history comment
- `backend/run.py`: added `warnings.warn(DeprecationWarning)` on startup — Flask removal scheduled Sprint-03
- `CLAUDE.md`: updated all port 5000 references to reflect Flask=deprecated, FastAPI=active
- `docs/architecture.md`: added Backend Status table (FastAPI active, Flask deprecated)
  **Flag (not fixed — needs separate prompt):** `frontend/services/api.ts` line 22 has a hardcoded `localhost:5000` string inside the network error message. The API URL itself is correctly read from `VITE_API_URL`; only the error message text is stale.
  **Result:** `grep -rn "localhost:5000" frontend/services/` returns zero hits on the functional URL path.
  **Files affected:** frontend/.env.local (new), frontend/.env.example, backend/run.py, CLAUDE.md, docs/architecture.md, docs/changelog.md

---

## 2026-06-19 — BSA-10 / TD-031: FastAPI integration tests with httpx

**Type:** Testing infrastructure
**Change:** Added full pytest suite for the FastAPI backend (backend-v2/). 7 unit tests run against an in-process ASGI transport — no server required.

- `conftest.py`: `AsyncClient` fixture via `ASGITransport` (same pattern as Flask's `test_client()`)
- `tests/test_health.py`: 2 tests — status 200 + JSON shape
- `tests/test_analyze.py`: 5 tests — CSV upload, response shape, bad extension (400), oversized file (413), required transaction fields
- `tests/test_parity.py`: shape-parity test between Flask and FastAPI (marked `integration`; requires both servers running, excluded from standard CI)
- `tests/fixtures/sample.csv`: 5-row minimal real-looking bank statement fixture
- `pyproject.toml`: added `asyncio_mode = "auto"` and `asyncio_default_fixture_loop_scope = "function"` to suppress pytest-asyncio deprecation warning; added `integration` marker
  **Result:** 7 passed, 0 warnings. Unblocks BSA-09 (Flask cutover).
  **Files affected:** backend-v2/conftest.py (new), backend-v2/tests/**init**.py (new), backend-v2/tests/test_health.py (new), backend-v2/tests/test_analyze.py (new), backend-v2/tests/test_parity.py (new), backend-v2/tests/fixtures/sample.csv (new), backend-v2/pyproject.toml

---

## 2026-06-19 — Bug fix: Merchant insights showing raw account numbers; account details not extracted

**Type:** Bug fix
**Root cause 1 (merchant insights):** `TransactionPatternTrainer.analyze()` fell back to `receiver_details.account` — a raw numeric string extracted from narrations (e.g. "609386161826") — as a merchant key when no named merchant was found. This produced dozens of meaningless numeric entries in the merchant insights panel.
**Fix:** Removed `receiver_details.account` from the merchant fallback chain. Now only uses `receiver_details.name` if it contains at least 2 alphabetic characters; otherwise groups as "UNKNOWN".
**Root cause 2 (account details):** The first phone pattern in `_extract_metadata_from_text` (`\b(?:\+91[-\s]?)?[6-9]\d{9}\b`) had no capture group. When a phone number appeared in the CSV metadata rows, `match.group(1)` raised `IndexError`, silently crashing the entire metadata extraction and returning `{}` for all account info fields.
**Fix:** Replaced the broken phone patterns with labeled-keyword patterns that always have a capture group. Also fixed `account_holder` patterns: removed the overly strict lookahead (`(?=\s*(?:account|bank|...))` that almost never matched); added simpler `customer name:` / `account holder name:` patterns. Moved hardcoded bank name list to first position in `bank_name` patterns (most reliable).
**Files affected:** backend/app/models/analyzeModel.py, backend-v2/app/models/analyzer.py

---

## 2026-06-13 — TD-028: Replace hardcoded reload=True with UVICORN_RELOAD env var

**Type:** Bug fix
**Change:** `backend-v2/run.py` read `UVICORN_RELOAD` env var (default `"false"`) instead of hard-coding `reload=True`. Mirrors the Flask `debug=True` fix from Sprint-01. In production, hot-reload causes double-startup and exposes Uvicorn internals.
**Files affected:** backend-v2/run.py

---

## 2026-06-13 — TD-029: Remove dead `import requests` from FastAPI analyzer

**Type:** Cleanup
**Change:** Removed `import requests` from `backend-v2/app/models/analyzer.py` and `requests==2.32.5` from `backend-v2/requirements.txt`. The only caller (`verify_bank_account_with_pennyless`) was deleted in Sprint-01; the import was never cleaned up in the FastAPI copy.
**Files affected:** backend-v2/app/models/analyzer.py, backend-v2/requirements.txt

---

## 2026-06-13 — TD-030: Fix CORS wildcard + credentials violation in FastAPI

**Type:** Bug fix
**Change:** Replaced `allow_methods=["*"]` and `allow_headers=["*"]` with explicit lists (`["GET", "POST", "OPTIONS"]` and `["Content-Type", "Authorization"]`) in `backend-v2/app/main.py`. The CORS spec forbids wildcards when `allow_credentials=True`; this would silently break once auth is added.
**Files affected:** backend-v2/app/main.py

---

## 2026-06-13 — TD-032: Anchor UPLOAD_DIR to file location in FastAPI router

**Type:** Bug fix
**Change:** `UPLOAD_DIR` in `backend-v2/app/routers/analyze.py` changed from `Path("uploads")` (relative to launch CWD) to `Path(__file__).parent.parent.parent / "uploads"` (always resolves to `backend-v2/uploads/` regardless of where uvicorn is launched from).
**Files affected:** backend-v2/app/routers/analyze.py

---

## 2026-05-31 — BSA-03: Port POST /api/analyze/bank/statement to FastAPI

**Type:** Feature (migration)
**Change:** Added /api/analyze/bank/statement to FastAPI backend (backend-v2). BankStatementAnalyzer runs inside asyncio.to_thread() so CPU-bound parsing never blocks the event loop. File validation (extension whitelist, 20 MB size cap) and cleanup (finally-block unlink) mirror the Flask controller exactly. Flask backend unchanged and still running on port 5000.
**Files affected:** backend-v2/app/routers/analyze.py (new), backend-v2/app/models/analyzer.py (new), backend-v2/app/main.py

---

## 2026-05-31 — BSA-02: FastAPI scaffold (backend-v2/)

**Type:** Feature (migration scaffold)
**Change:** Created backend-v2/ with FastAPI app, pydantic-settings config, Pydantic schemas mirroring frontend types.ts, /api/health endpoint, Swagger UI at /docs. Flask backend unchanged and still running on port 5000.
**Files affected:** backend-v2/ (new directory — all files)

---

## 2026-05-31 — TD-016: Stand up pytest with core unit tests

**Type:** Testing infrastructure
**Change:** Added pytest==8.3.5 + pytest-flask==1.3.0; test suites for parse_amount (9 cases), normalize_date (7 cases), analyze_narration_details (6 cases + 1 xfail), and /api/health. Added backend/conftest.py with Flask test client fixture. Result: 23 passed, 1 xfailed.
**Bug found and fixed:** parse_amount Cr./Dr. regex had a trailing \b that cannot anchor after a non-word character (the dot) at end-of-string — only "Cr" was stripped, leaving a stray "." that broke float(). Fixed by removing the trailing \b from the substitution pattern.
**xfail documented:** UPI structured match returns early before merchant detection — "UPI/.../AMAZON PAY/..." returns merchant=None. Marked xfail pending a fix.
**Files affected:** backend/requirements.txt, backend/conftest.py, backend/tests/**init**.py, backend/tests/test_parse_amount.py, backend/tests/test_normalize_date.py, backend/tests/test_narration.py, backend/tests/test_health.py, backend/app/models/analyzeModel.py (regex fix)

---

## 2026-05-31 — TD-027: Add GET /api/health endpoint

**Type:** Feature (monitoring)
**Change:** Added /health route on the blueprint (resolves to GET /api/health) returning {"status": "ok", "service": "bank-statement-analyzer"}. Note: route is defined as /health (not /api/health) because the blueprint is registered with url_prefix="/api".
**Reason:** Unblocks container health checks and uptime monitoring. Explicit ADR action item.
**Files affected:** backend/app/routes/routes.py, docs/changelog.md

---

## 2026-05-31 — TD-022 + TD-020: Delete dead Pennyless fn; fix .gitignore

**Type:** Security cleanup + repo fix
**TD-022:** Deleted verify_bank_account_with_pennyless — dead code shipping hardcoded identity data (name="stco", mobile="9999999999"). Never called; Config.INTEGRATION_URL and INTEGRATION_AUTH are defined but the fn should not live in the codebase until the integration is real.
**TD-020:** Renamed .gitIgnore → .gitignore; added missing patterns for **pycache**, venv/, uploads/, node_modules/. Note: Windows filesystem is case-insensitive so the rename was done as delete-then-recreate.
**Files affected:** backend/app/models/analyzeModel.py, .gitignore

---

## 2026-05-31 — TD-001 Fix: requirements.txt re-encoded as UTF-8

**Type:** Bug fix (reopened)
**Root cause:** Fix was logged on 2026-05-29 but the file on disk was never rewritten; PowerShell or the editor re-saved as UTF-16-LE.
**Fix:** Rewrote via Python open(..., encoding='utf-8') to guarantee encoding.
**Files affected:** backend/requirements.txt, docs/changelog.md

---

## 2026-05-30 — Session 02: Re-review + Forward Planning

### Documentation — Current-state re-review

**Type:** Documentation / review
**Decision:** Regenerated `code-review.md` and `tech-debt.md` against the post-Sprint-01 code; added `improvement-analysis.md` reviewing the planned PDF / FastAPI / AI-ML tracks.
**Reason:** The 2026-05-29 docs described the pre-fix codebase. Verified which fixes actually landed.
**Impact:**

- Confirmed 13 tech-debt items genuinely resolved (TD-002–006, 009–015, 017).
- **Reopened TD-001:** `requirements.txt` is still UTF-16 on disk — the fix was logged but never landed. `pip install` still fails on a clean env. Now the #1 open item; recommend a CI guard against regression.
- Logged 7 new debt items (TD-021–027): multi-page PDF row loss, dead Pennyless fn with hardcoded identity data, byte-level upload validation, transaction dedupe, over-greedy txn_reference regex, balance-less confidence penalty, missing /api/health.
- Raised TD-016 (no tests) priority — prerequisite for the FastAPI port and ML work.
  **Strategic finding:** three unplanned prerequisites block the AI/ML roadmap as written — persistence (history store), PII redaction before LLM calls, and an evaluation harness. Recommended building this substrate before the planned features.
  **Files affected:** `docs/code-review.md`, `docs/tech-debt.md`, `docs/improvement-analysis.md` (new), `docs/changelog.md`

---

## 2026-05-29 — Session 01: Full Audit + Critical Fixes

### Architecture Decision

**Type:** Architecture decision  
**Decision:** Migrate backend from Flask to FastAPI  
**Reason:** LLM streaming (SSE/WebSocket) requires ASGI; Pydantic eliminates manual validation; auto-generated OpenAPI docs improve DX  
**Impact:** New `backend-v2/` directory will be created; Flask stays running in parallel during migration  
**Files affected:** `docs/adr-001-flask-vs-fastapi.md` (created)

---

### Bug Fix — requirements.txt UTF-16 encoding

**Type:** Bug fix  
**Root cause:** File was saved as UTF-16 — `pip install -r requirements.txt` would fail on any standard environment  
**Fix:** Regenerated as clean UTF-8 with minimal direct dependencies only  
**Files affected:** `backend/requirements.txt`

---

### Bug Fix — Config.INTEGRATION_URL/AUTH undefined

**Type:** Bug fix  
**Root cause:** `verify_bank_account_with_pennyless()` referenced `Config.INTEGRATION_URL` and `Config.INTEGRATION_AUTH` which were never defined in the Config class — would raise `AttributeError` at runtime  
**Fix:** Added both to Config class with empty string defaults; added `MAX_UPLOAD_SIZE` too  
**Files affected:** `backend/app/config/config.py`

---

### Security Fix — debug=True hardcoded

**Type:** Security fix  
**Root cause:** `app.run(debug=True)` hard-coded in `run.py` — exposes Werkzeug interactive debugger in any environment  
**Fix:** Debug mode now reads from `FLASK_DEBUG` environment variable; defaults to `false`  
**Files affected:** `backend/run.py`

---

### Security Fix — uploaded files never deleted

**Type:** Security + reliability fix  
**Root cause:** Files saved to `uploads/` had no cleanup — sensitive financial data accumulated on disk indefinitely  
**Fix:** Added `finally` block in controller to `os.remove(file_path)` after every request (success or failure)  
**Files affected:** `backend/app/controllers/analyzeController.py`

---

### Security Fix — no file validation

**Type:** Security fix  
**Root cause:** Only checked if filename was empty; no extension whitelist, no size limit, no MIME check  
**Fix:** Extension whitelist `{.pdf, .csv, .xlsx, .xls}`, 20 MB size check, UUID prefix on saved filenames  
**Files affected:** `backend/app/controllers/analyzeController.py`

---

### Bug Fix — confidence_score missing from PDF path

**Type:** Bug fix  
**Root cause:** `_process_excel_csv()` computed confidence scores for all transactions; `_process_pdf_transactions()` did not. PDF transactions returned without `confidence_score` field, breaking frontend type contract.  
**Fix:** Added confidence scoring loop + `confidence_summary` block to PDF path  
**Files affected:** `backend/app/models/analyzeModel.py`

---

### Bug Fix — `and` should be `or` in PDF column check

**Type:** Bug fix  
**Root cause:** `if not all(required_cols_pdf) and not (credit_col or debit_col or amount_col)` — the `and` made the guard weaker than intended; a table missing only date/narration would not be skipped. Excel path correctly used `or`.  
**Fix:** Changed `and` → `or` to match Excel path logic  
**Files affected:** `backend/app/models/analyzeModel.py`

---

### Cleanup — removed 4 dead classes

**Type:** Code cleanup  
**Removed:** `EnhancedNarrationAnalyzer`, `TransactionPatternLearner`, `BalanceValidator`, `EnhancedConfidenceScorer`  
**Reason:** Never instantiated or called; contained bugs (`self.nlp` undefined, string dates accessed as `.day`); 200+ lines of noise  
**Files affected:** `backend/app/models/analyzeModel.py`

---

### Cleanup — removed scikit-learn imports

**Type:** Dependency cleanup  
**Removed:** `TfidfVectorizer`, `MultiLabelBinarizer`, `RandomForestClassifier` imports  
**Reason:** Not used anywhere in active code; `scikit-learn` + `scipy` = ~120 MB unused dependency  
**Note:** Will be re-added when ML categorization features are built (Sprint 02+)  
**Files affected:** `backend/app/models/analyzeModel.py`, `backend/requirements.txt`

---

### Cleanup — replaced all print() with logging

**Type:** Code quality  
**Change:** All `print()` statements in `analyzeModel.py` replaced with `logger.debug/warning/error`  
**Reason:** `print()` doesn't support log levels or structured output; `%s` format with print produces garbled output  
**Files affected:** `backend/app/models/analyzeModel.py`, `backend/app/__init__.py`

---

### Cleanup — fixed double assignment typo

**Type:** Code quality  
**Change:** `parsed_date = parsed_date = self.normalize_date(...)` → `parsed_date = self.normalize_date(...)`  
**Files affected:** `backend/app/models/analyzeModel.py`

---

### Cleanup — removed dead variables

**Type:** Code quality  
**Removed:** `verification_tasks = []` and `txn_peer_map = []` (initialized but never used)  
**Files affected:** `backend/app/models/analyzeModel.py`

---

### Feature — frontend API URL from env var

**Type:** Feature / config fix  
**Change:** `const API_URL = 'http://localhost:5000...'` → `const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:5000'`  
**Reason:** Hardcoded URL prevents pointing frontend at staging or production  
**Files affected:** `frontend/services/api.ts`

---

### Documentation — added .env.example files

**Type:** Documentation  
**Files created:** `backend/.env.example`, `frontend/.env.example`

---

### Documentation — full docs/ folder created

**Type:** Documentation  
**Files created:** `docs/architecture.md`, `docs/system-design.md`, `docs/tech-debt.md`, `docs/code-review.md`, `docs/adr-001-flask-vs-fastapi.md`, `docs/ml-ai-brainstorm.md`, `docs/sprint-01-plan.md`, `docs/requirements.md`, `docs/changelog.md`

---

### Process — AI development workflow defined

**Type:** Process  
**Decision:** All implementation via Claude Code; Cowork Claude handles prompts, planning, and study docs. Changes made in small patches. Study doc written after every sprint.  
**Files affected:** `CLAUDE.md` (workflow section added), `docs/dev-process.md` (created)
