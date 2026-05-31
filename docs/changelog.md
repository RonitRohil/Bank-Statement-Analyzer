# Changelog — Bank Statement Analyzer

All notable changes to this project are documented here.  
Format: `[Date] — [Type] — [Short description]`

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
