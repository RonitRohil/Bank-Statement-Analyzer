# Code Review — Bank Statement Analyzer

**Reviewed by:** Claude (Cowork)  
**Sprint:** Sprint-01 (BSA-02, BSA-03, TD-016, TD-027)  
**Review date:** 2026-06-13  
**Scope:** FastAPI migration (`backend-v2/`), pytest suite (`backend/tests/`), Sprint-01 bug fixes

> Previous review covered the pre-fix Flask codebase (2026-05-29/30). This review focuses on what Sprint-01 actually shipped — the FastAPI scaffold and analyze endpoint — plus newly discovered issues across both backends.

---

## Sprint-01 Completion Check

| Task | Shipped? | Notes |
|------|----------|-------|
| BSA-01 — Critical fixes (TD-001→TD-027) | ✅ | All 13 carried items resolved; TD-001 re-encoded (again) |
| BSA-02 — FastAPI scaffold | ✅ | `backend-v2/` with Pydantic settings, CORS, schemas, health endpoint |
| BSA-03 — Port analyze endpoint | ✅ | `asyncio.to_thread` pattern correct; file lifecycle mirrored |
| TD-016 — pytest | ✅ | 23 passed, 1 xfail; test files for parse_amount, normalize_date, narration, health |
| TD-027 — Flask `/api/health` | ✅ | Returns `{"status": "ok", "service": "bank-statement-analyzer"}` |
| TD-022 — Delete Pennyless fn | ✅ | Deleted from Flask side; **not yet cleaned from `backend-v2/analyzer.py`** |
| TD-020 — `.gitIgnore` rename | ✅ | Committed as delete + recreate |

---

## Summary

Sprint-01 delivered a solid FastAPI scaffold. The core design — `asyncio.to_thread` for blocking I/O, Pydantic models mirroring the frontend types, file lifecycle cleanup in `finally` — is all correct. The main concerns are three: a debug flag regression (same `reload=True` mistake as the original `debug=True`), a dead `requests` import that was supposed to be removed, and zero test coverage on the FastAPI routes themselves.

---

## Critical Issues

| # | File | Line | Issue | Severity |
|---|------|------|-------|----------|
| CR-S-01 | `backend-v2/run.py` | 3 | `reload=True` hardcoded — identical to the `debug=True` mistake fixed in Flask. Exposes file-watcher behaviour in production and can cause double-startup on some platforms. | 🔴 Critical |
| CR-C-01 | `backend-v2/app/models/analyzer.py` | 7 | `import requests` — dead import. `requests` was only used in `verify_bank_account_with_pennyless()` which was deleted on the Flask side. The import was never removed from the FastAPI copy. | 🔴 Critical |

**CR-S-01 Fix:**
```python
# run.py — before
uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

# run.py — after
import os
reload = os.getenv("UVICORN_RELOAD", "false").lower() == "true"
uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=reload)
```

**CR-C-01 Fix:**
```python
# Remove line 7 from backend-v2/app/models/analyzer.py:
import requests   # DELETE THIS

# Also remove from backend-v2/requirements.txt:
requests==2.32.5  # DELETE THIS
```

---

## High-Priority Issues

| # | File | Issue | Category |
|---|------|-------|----------|
| CR-H-01 | `backend-v2/app/main.py` | CORS: `allow_credentials=True` combined with `allow_methods=["*"]` and `allow_headers=["*"]` is spec-violating. When credentials are enabled, browsers refuse wildcard `*` for methods/headers — use explicit lists. | Security |
| CR-H-02 | `backend-v2/` (no test dir) | Zero integration tests for FastAPI routes. The pytest suite only covers Flask. Both `/api/analyze/bank/statement` and `/api/health` are completely untested on the FastAPI side. | Testing |
| CR-H-03 | `backend-v2/app/routers/analyze.py` | `UPLOAD_DIR = Path("uploads")` is a module-level relative path resolved at import time. If uvicorn is launched from the project root instead of `backend-v2/`, uploads land in the wrong directory. | Correctness |

**CR-H-01 Fix:**
```python
# main.py — explicit CORS instead of wildcards
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
```

**CR-H-03 Fix:**
```python
# analyze.py — anchor to file location, not cwd
UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
```

---

## Suggestions

| # | File | Suggestion | Category |
|---|------|------------|----------|
| CR-M-01 | `backend-v2/app/routers/analyze.py` | Replace `asyncio.to_thread(lambda: BankStatementAnalyzer(str(file_path)).extract_transactions())` with two explicit lines: construct the analyzer, then `await asyncio.to_thread(analyzer.extract_transactions)`. Easier to read and to set a breakpoint on. | Maintainability |
| CR-M-02 | `backend-v2/app/models/analyzer.py` | Full copy of Flask's `analyzeModel.py` minus 3 imports — drift is guaranteed. Track as TD-007; resolve at BSA-09 cutover by extracting to a shared `core/` package. | Maintainability |
| CR-M-03 | `backend-v2/app/main.py` | Lifespan logs startup but not shutdown. Add `logger.info("shutting down")` after `yield`. | Maintainability |
| CR-M-04 | `backend-v2/app/routers/health.py` | Health endpoint is sync `def` while all other routes are `async def`. FastAPI handles it correctly (runs on thread pool), but use `async def` for consistency. | Style |
| CR-P-01 | `backend-v2/app/routers/analyze.py` | `content = await file.read()` + `file_path.write_bytes(content)` peaks at ~2x file size in RAM. For 20 MB files that's ~40 MB. Acceptable at current scale; consider `aiofiles` streaming if this endpoint gets high concurrency. | Performance |
| CR-C-02 | `backend-v2/app/models/schemas.py` | `Transaction.account` field name is ambiguous — it could mean the account holder's account or the counterparty account. Rename to `counterparty_account` to avoid confusion with `AccountInfo.account_number`. | Correctness |

---

## What Looks Good

- **`asyncio.to_thread` usage is correct.** The lambda captures `file_path` and the BankStatementAnalyzer is purely synchronous — wrapping it is exactly right. The event loop stays unblocked during pandas/pdfplumber work.
- **File lifecycle is solid.** `try/finally` with `file_path.exists()` guard mirrors the Flask fix precisely. Both success and exception paths clean up the temp file.
- **`pydantic-settings` for config** is a real upgrade over the hand-rolled `Config` class in Flask. Env var injection, type coercion, and `.env` file support come for free.
- **`AnalyzeResponse` schema mirrors frontend types.** The `StatementPeriod` alias trick (`from_date` field with `alias="from"`) handles the Python keyword conflict without breaking the JSON contract.
- **Pydantic v2 throughout.** `model_config = ConfigDict(...)` instead of the deprecated class `Config` — up to date with the current API.
- **`response_model=AnalyzeResponse` on the route.** The response dict from `extract_transactions()` has the correct top-level shape (`success`, `status_code`, `message`, `result`). FastAPI's response validation will catch schema drift at runtime.
- **Swagger UI at `/docs` for free.** Immediately testable without Postman or curl. Big DX win.
- **`populate_by_name=True` on `StatementPeriod`** — both alias and field name populate the model. Defensive and correct.

---

## Verdict

**Request Changes** — Two critical issues must be fixed before BSA-09 (Flask cutover):

1. `reload=True` → env-controlled (CR-S-01)
2. `import requests` + `requests` in requirements.txt → delete (CR-C-01)

The CORS wildcard (CR-H-01) and upload-path anchor (CR-H-03) should go in the same patch. FastAPI integration tests (CR-H-02) are Sprint-02 P0.

---

## Flask Backend — Carried Issues

The Flask backend (`backend/`) was not modified this sprint. These issues remain open in `tech-debt.md` and are **inherited by `backend-v2/analyzer.py`** since it is a copy:

- **TD-021** — Multi-page PDF continuation rows dropped (silent data loss)
- **TD-024** — No transaction deduplication
- **TD-025** — `transaction_reference` regex too greedy
- **TD-026** — Confidence score penalizes balance-less formats incorrectly
- **TD-007** — `BankStatementAnalyzer` is ~1,280 lines in one class

---

*Tech debt: `docs/tech-debt.md` · Sprint plan: `docs/sprint-01-plan.md` · Architecture: `docs/architecture.md`*
