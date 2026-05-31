# Skill Input Prompts — Sprint 01 Review

**Generated:** 2026-05-31  
**By:** Cowork Claude  
**Purpose:** Ready-to-paste input prompts for three skills. Paste each block directly into
the corresponding skill invocation.

---

## 1. `/engineering:code-review`

> Paste the text below when invoking the skill.

---

**What to review:** Sprint 01 changes to Bank Statement Analyzer — a Flask + React/TypeScript
app for parsing bank statements (PDF, CSV, XLSX). I have not run the code yet; this is a
pre-test review. Focus on correctness, bugs, and gaps — not style.

**Context:** The sprint had two tracks:
1. Bug/debt fixes to the existing Flask backend (`backend/`)
2. A new FastAPI backend scaffold (`backend-v2/`) including a ported analyze endpoint

**Files changed / created this sprint:**

Flask backend fixes (`backend/`):
- `app/routes/routes.py` — added `GET /api/health` endpoint
- `app/controllers/analyzeController.py` — file validation, UUID filenames, cleanup
- `app/models/analyzeModel.py` — removed dead classes, fixed bugs (see changelog)
- `app/__init__.py` — logging setup
- `tests/conftest.py` — pytest Flask test client setup
- `tests/test_parse_amount.py`
- `tests/test_normalize_date.py`
- `tests/test_narration.py`
- `tests/test_health.py`

FastAPI backend (`backend-v2/` — all new):
- `app/main.py`
- `app/config/settings.py`
- `app/models/schemas.py`
- `app/models/analyzer.py` (copy of Flask's analyzeModel.py with Flask imports stripped)
- `app/routers/health.py`
- `app/routers/analyze.py`
- `requirements.txt`
- `run.py`

**Known issues I already spotted (review these carefully):**

1. `backend-v2/app/routers/analyze.py` line 46:
   ```python
   return JSONResponse(content=result, status_code=200)
   ```
   `result` is the dict returned by `BankStatementAnalyzer.extract_transactions()`, which
   already contains a `"status_code"` field (200, 400, or 500) depending on parse success.
   The HTTP response status is hardcoded to `200` regardless — so a parse failure that
   returns `{"success": 0, "status_code": 500, ...}` gets an HTTP 200. Flask does NOT have
   this bug. Confirm the fix: use `result.get("status_code", 200)` as the HTTP status.

2. `backend-v2/app/main.py` line 29:
   ```python
   @app.on_event("startup")
   async def on_startup():
   ```
   `@app.on_event()` is deprecated since FastAPI 0.93. Should use the `lifespan` context
   manager pattern. Confirm whether this causes runtime warnings.

3. `backend-v2/app/models/schemas.py` defines `AnalyzeResponse` and `ErrorResponse` but
   `analyze.py` returns a raw `JSONResponse` with no Pydantic validation. The main DX reason
   to migrate to FastAPI (typed contracts, Swagger docs showing response shape) is currently
   bypassed. Is this intentional for now or a gap?

4. `backend/tests/` has no `pytest.ini`, `pyproject.toml`, or `setup.cfg`. No `[tool.pytest]`
   config means: (a) test discovery paths must be specified manually, (b) `conftest.py` in
   `backend/` root may not be picked up reliably depending on invocation directory. Confirm
   test discovery works with `python -m pytest tests/ -v` from `backend/`.

5. `backend/requirements.txt` is still UTF-16-LE on disk (binary encoding). `pytest` and
   `pytest-flask` are presumably in the active venv but are NOT persisted in requirements.txt
   in a way that `pip install -r requirements.txt` on a clean machine would pick up. Any CI
   or new contributor will get missing test deps.

**Additional things to check during review:**

- `backend-v2/app/routers/analyze.py` line 15: `UPLOAD_DIR = Path("uploads")` is resolved
  relative to CWD at import time. If uvicorn is started from any directory other than
  `backend-v2/`, uploads will land in the wrong place or fail to create. Same issue exists
  in Flask. Is there a safer way (e.g., `Path(__file__).parent.parent / "uploads"`)?

- `backend/app/routes/routes.py`: health route is attached to `analyze_statement_bp` (the
  analyze blueprint). Health has nothing to do with analysis. Minor separation-of-concerns
  issue — is it worth splitting into its own blueprint now?

- `backend-v2/app/models/analyzer.py` is a copy of `backend/app/models/analyzeModel.py`
  with Flask imports stripped. These two files will diverge immediately — any fix to the
  analyzer in Flask must also be manually applied to backend-v2. Is there a plan to
  deduplicate (shared package, symlink, or submodule) before the migration completes?

- `test_narration.py` marks `test_amazon_merchant_in_upi_narration` as `xfail` with a comment
  that UPI structured match returns early before merchant detection. This is a real functional
  gap: UPI payments to Amazon don't get a merchant tag. Is this tracked as a tech debt item?

**Response format I need:**
- Critical bugs (will break at runtime)
- High issues (wrong behavior, test gaps, won't catch regressions)
- Medium/low (code quality, maintainability, DX)
- For each: which file + line, what the problem is, suggested fix

---

## 2. `/engineering:tech-debt`

> Paste the text below when invoking the skill.

---

**Project:** Bank Statement Analyzer — Flask + React/TypeScript, migrating to FastAPI.

**Purpose:** Update the tech debt backlog after Sprint 01. We need to:
1. Mark confirmed-resolved items closed
2. Reopen or amend items that were partially fixed
3. Add newly discovered debt from the sprint's code review
4. Reprioritize the remaining open items given the FastAPI migration is now underway

**Current tech debt doc:** `docs/tech-debt.md` (has IDs TD-001 through TD-027)

**Sprint 01 resolution status (verified against actual files on disk):**

| ID | What it was | Actual status |
|----|-------------|---------------|
| TD-001 | requirements.txt UTF-16 | ❌ STILL OPEN — file still binary UTF-16 on disk |
| TD-016 | No tests | ✅ RESOLVED — 4 test files + conftest.py created |
| TD-020 | .gitIgnore capitalized | ⚠️ PARTIAL — .gitignore (lowercase) now exists BUT .gitIgnore (cap I) also still exists alongside it |
| TD-022 | Dead Pennyless fn | ✅ RESOLVED — deleted from both analyzeModel.py and analyzer.py |
| TD-027 | No /api/health | ✅ RESOLVED — added to Flask routes.py (GET /health on /api blueprint = /api/health) |
| BSA-02 | FastAPI scaffold | ✅ DONE — backend-v2/ fully scaffolded |
| BSA-03 | Analyze endpoint ported | ✅ DONE — analyze.py with asyncio.to_thread |

**New debt introduced this sprint:**

1. **HTTP status mismatch in FastAPI analyze endpoint** — `analyze.py` returns
   `JSONResponse(content=result, status_code=200)` regardless of analyzer outcome.
   The analyzer already puts `status_code` (200/400/500) in the result dict, but the
   HTTP response always comes back HTTP 200. Flask doesn't have this bug.
   Severity: 🔴 High — clients that check HTTP status (curl, frontend error handling)
   will miss errors.

2. **`@app.on_event("startup")` deprecated** — FastAPI 0.93+ deprecated this pattern;
   lifespan context manager is the replacement. Currently produces deprecation warnings.
   Severity: 🟡 Medium — not broken, but will become an error in a future FastAPI version.

3. **`AnalyzeResponse` Pydantic schema unused** — Defined in schemas.py but analyze.py
   returns raw `JSONResponse`, bypassing Pydantic response validation entirely. The primary
   DX gain of FastAPI (typed response contract + auto Swagger docs with response shape) is
   not realized. Severity: 🟡 Medium — not broken, but negates a key FastAPI benefit.

4. **No pytest configuration file** — No `pytest.ini` or `pyproject.toml` in backend/.
   Test discovery relies on implicit path conventions; running `pytest` from a non-standard
   directory silently finds nothing. `pytest` and `pytest-flask` are in the venv but not in
   `requirements.txt` (which is still UTF-16 anyway — see TD-001).
   Severity: 🟠 High — CI will fail; new contributors can't run tests from requirements.txt.

5. **analyzer.py is a copied file, not a shared module** — `backend-v2/app/models/analyzer.py`
   is a manual copy of `backend/app/models/analyzeModel.py`. Any fix to the analyzer must be
   applied in two places. Will cause drift immediately.
   Severity: 🟠 High — regression risk during the migration window; creates a false sense of
   parity (the two files can silently diverge).

6. **UPLOAD_DIR is CWD-relative** (both backends) — `Path("uploads")` is relative to whatever
   directory the process starts from. Both backends are documented to require launching from
   their own directory, but there's no guard or absolute-path fallback.
   Severity: 🟡 Medium — documented but fragile; silent data-loss risk in production.

**Existing open items to reassess priority on:**
- TD-007 (monolithic 1,280-line class) — now even more relevant: we have two copies of it
- TD-008 (column detection duplicated) — same; fix in one copy must be applied to both
- TD-021 (multi-page PDF row loss) — still open; affects both backends equally
- TD-024 (no transaction dedupe) — still open; pre-requisite for persistence layer
- TD-025 (txn_reference over-greedy regex) — still open

**What I need from the tech-debt review:**
- Updated status table with the above changes applied
- Assign severity and priority to the 6 new items, with IDs (TD-028 onward)
- Flag which open items are now blockers for Sprint 02 work (persistence layer, eval harness,
  LLM features)
- Recommended Sprint 02 slice (top 5–6 items to close, ordered by priority)

---

## 3. `/product-management:sprint-planning`

> Paste the text below when invoking the skill.

---

**Project:** Bank Statement Analyzer (side project / personal finance tool)  
**Sprint:** Sprint 02  
**Dates:** 2026-06-13 → 2026-06-26 (2 weeks)  
**Available capacity:** ~10 hours (evenings + weekends)

**Sprint 01 recap — what shipped:**
- ✅ All critical Flask bug fixes (TD-002 through TD-017 batch)
- ✅ FastAPI backend scaffold (`backend-v2/`)
- ✅ `/api/analyze/bank/statement` ported to FastAPI with asyncio.to_thread
- ✅ `/api/health` endpoint on Flask
- ✅ Basic pytest suite (parse_amount, normalize_date, narration enrichment, health)
- ✅ Dead code deleted (Pennyless fn, 4 dead classes from Sprint 00)
- ✅ `.gitignore` fixed

**Sprint 01 carry-overs (not done):**
- ❌ TD-001: `requirements.txt` still UTF-16 on disk — pip install fails on clean env
- ❌ TD-020 partial: `.gitIgnore` (cap I) still coexists with `.gitignore`

**New debt introduced in Sprint 01 (needs fixing):**
- HTTP status always 200 from FastAPI endpoint (even on parse errors)
- `@app.on_event("startup")` deprecated in FastAPI — needs lifespan migration
- `AnalyzeResponse` schema unused — no response validation in FastAPI
- No `pytest.ini` / pyproject.toml — test discovery broken for CI / new contributors
- `analyzer.py` is a manual copy of `analyzeModel.py` — divergence risk

**Current architecture state:**
- Flask backend (port 5000) — production path, all fixes landed
- FastAPI backend (port 8000) — scaffolded + analyze endpoint ported, NOT frontend-connected
- Frontend still points to Flask via `VITE_API_URL`
- Next step for migration: fix FastAPI bugs → run parity test → update frontend → decommission Flask (BSA-09)

**Strategic context for Sprint 02 (from `docs/improvement-analysis.md`):**
Three prerequisites must be built before the AI/ML feature roadmap can execute:
1. **Persistence layer** — the app is stateless; anomaly detection, recurring detection,
   and forecasting all require stored transaction history. SQLite to start.
2. **Evaluation harness** — no labeled test fixtures, no accuracy metric. Can't know if
   a regex/ML change helps or hurts.
3. **PII redaction** — any LLM feature (categorization fallback, Q&A, summary) will send
   narrations containing names, account numbers, VPAs to a third-party API. Must redact first.

**Candidate backlog for Sprint 02:**

| ID | Item | Category | Est. | Priority |
|----|------|----------|------|----------|
| TD-001 | Fix requirements.txt UTF-16 + add CI guard | Debt | 15 min | P0 carry-over |
| TD-020 | Delete remaining .gitIgnore (cap I) | Debt | 5 min | P0 carry-over |
| NEW | Fix FastAPI HTTP status (analyze.py) | Bug | 30 min | P0 — ships broken behavior |
| NEW | Migrate @on_event → lifespan | Debt | 30 min | P1 |
| NEW | Wire AnalyzeResponse into analyze.py | Debt | 1h | P1 |
| NEW | Add pytest.ini + pytest/pytest-flask to requirements.txt | Infra | 30 min | P1 |
| BSA-09 | Frontend cutover to FastAPI + decommission Flask | Migration | 1h | P1 — completes migration |
| NEW | Persistence layer (SQLite) — accounts, statements, transactions | Feature | 4h | P2 — unlocks ML roadmap |
| NEW | Evaluation harness — fixture statements + evaluate.py | Testing | 3h | P2 — unlocks ML |
| BSA-04 | LLM categorization fallback (Claude Haiku for null categories) | Feature | 1h | P3 — needs redaction first |
| TD-021 | Multi-page PDF row loss (carry-forward header) | Bug | 2h | P2 |
| TD-024 | Transaction deduplication before scoring | Bug | 1h | P2 |

**Questions for sprint planning:**
1. Is BSA-09 (Flask decommission) a P0 or P1? The FastAPI endpoint is untested against real
   files — we need a parity test before cutting over.
2. Should persistence be Sprint 02 or Sprint 03? It's 4h of the 10h capacity — it's the right
   investment but it's substantial.
3. LLM features (BSA-04/05/06) depend on both persistence AND redaction. Should they be
   planned for Sprint 03 explicitly?
4. The `analyzer.py` copy-problem — should the fix (shared package or dedup) be in Sprint 02
   or wait until Flask is decommissioned?

**What I need from sprint planning:**
- Prioritized Sprint 02 task list with clear P0/P1/P2 tiers
- Capacity allocation (I have ~10h)
- Explicit carry-overs from Sprint 01 at P0
- Decision on whether to include persistence layer or push to Sprint 03
- A "definition of done" for BSA-09 (Flask decommission) that's safe to execute

---

## Summary of Bugs Found (for quick reference)

| Severity | File | Issue |
|----------|------|-------|
| 🔴 | `backend-v2/app/routers/analyze.py:46` | HTTP status always 200; error responses get HTTP 200 |
| 🔴 | `backend/requirements.txt` | Still UTF-16; pip install fails; pytest deps not persisted |
| 🟠 | `backend-v2/app/models/` | `analyzer.py` is manual copy of `analyzeModel.py` — divergence risk |
| 🟠 | `backend/tests/` | No `pytest.ini`/`pyproject.toml`; test discovery not configured |
| 🟡 | `backend-v2/app/main.py:29` | `@on_event("startup")` deprecated; use lifespan |
| 🟡 | `backend-v2/app/models/schemas.py` | `AnalyzeResponse` unused; no response validation in FastAPI |
| 🟡 | `backend-v2/app/routers/analyze.py:15` | `UPLOAD_DIR` CWD-relative; wrong if not launched from `backend-v2/` |
| 🟢 | `.gitIgnore` | Capital-I version still exists alongside lowercase `.gitignore` |
| 🟢 | `test_narration.py` | `xfail` test shows merchant detection gap for UPI narrations — not tracked as TD |
