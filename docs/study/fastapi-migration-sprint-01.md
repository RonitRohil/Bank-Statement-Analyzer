# Study Doc: FastAPI Migration — Sprint 01

**Sprint:** Sprint 01  
**Tasks covered:** BSA-02 (scaffold), BSA-03 (analyze endpoint), TD-027 (health endpoint)  
**Date:** 2026-05-31

---

## 1. What Was Built

Two components were added to `backend-v2/`:

**BSA-02 — FastAPI scaffold:**
- FastAPI app with CORS middleware, Pydantic-settings config, Swagger UI at `/docs`
- Pydantic schemas mirroring `frontend/types.ts`: `Transaction`, `AccountInfo`, `AnalysisResult`, `AnalyzeResponse`, `StatementPeriod`
- `GET /api/health` endpoint

**BSA-03 — Analyze endpoint:**
- `backend-v2/app/models/analyzer.py`: copy of the parsing engine (`BankStatementAnalyzer`, `TransactionPatternTrainer`) stripped of Flask-specific imports
- `backend-v2/app/routers/analyze.py`: `POST /api/analyze/bank/statement` as a FastAPI async route
- Flask backend (`backend/`) left running on port 5000 — zero changes

---

## 2. Why It Was Built

See [ADR-001](../adr-001-flask-vs-fastapi.md) for the full decision. Short version:

1. **LLM streaming** — future SSE/WebSocket endpoints need ASGI; Flask is WSGI and can't do it natively
2. **Pydantic** — eliminates hand-rolled request validation; auto-generates OpenAPI docs
3. **asyncio.to_thread** — the single biggest Flask pain point is that the pandas/pdfplumber parsing blocks the entire worker thread; FastAPI + to_thread solves this without Celery
4. **Developer experience** — Swagger UI at `/docs` is free; debugging is faster

---

## 3. How It Works

### File lifecycle in the analyze endpoint

```
Client → POST /api/analyze/bank/statement (multipart/form-data)
         ↓
         FastAPI reads file into memory: content = await file.read()
         ↓
         Validate extension ({.pdf, .csv, .xlsx, .xls}) — 400 if bad
         Validate size (≤ 20 MB default) — 413 if too large
         ↓
         Write to disk: UPLOAD_DIR / {uuid4().hex}{suffix}
         ↓
         asyncio.to_thread(lambda: BankStatementAnalyzer(path).extract_transactions())
         ↓  [runs in ThreadPoolExecutor — event loop unblocked]
         ↓
         result = plain Python dict (same shape as Flask response)
         ↓
         JSONResponse(content=result, status_code=200)
         ↓  [finally block always runs]
         file_path.unlink()  ← file deleted whether success or failure
```

### asyncio.to_thread pattern

`BankStatementAnalyzer.extract_transactions()` calls pandas and pdfplumber — both synchronous, CPU/IO bound. Calling them directly in an `async def` function would block the event loop and defeat the purpose of ASGI.

`asyncio.to_thread` submits the callable to Python's default `ThreadPoolExecutor` and `await`s it. The event loop remains free to serve other requests while parsing runs on a thread.

```python
result = await asyncio.to_thread(
    lambda: BankStatementAnalyzer(str(file_path)).extract_transactions()
)
```

The lambda is needed because `extract_transactions` is an instance method — `asyncio.to_thread` takes a zero-argument callable.

### Router registration

```python
# backend-v2/app/main.py
from app.routers import health, analyze
app.include_router(health.router)
app.include_router(analyze.router)
```

Each router uses `APIRouter()` and defines routes with the full path (`/api/analyze/bank/statement`), so no `prefix` is needed on the router — the path is explicit and matches the Flask route exactly.

### analyzer.py vs analyzeModel.py

`analyzeModel.py` (Flask) has two classes:
- `AnalyzeModel` — thin wrapper that calls `BankStatementAnalyzer` and wraps the result in Flask's `jsonify()`. Useless outside Flask.
- `BankStatementAnalyzer` — the actual parsing engine. Pure Python (pandas, pdfplumber, re). No Flask dependency in the class itself.

`analyzer.py` (FastAPI) contains only:
- `BankStatementAnalyzer` (identical logic)
- `TransactionPatternTrainer` (identical)

Three module-level Flask imports were dropped:
- `from flask import jsonify` — `BankStatementAnalyzer` never calls `jsonify`; the FastAPI router returns `JSONResponse` directly
- `from app.constants.constants import get_status_code` — replaced with inline integers (200, 400, 500)
- `from app.config.config import Config` — not used by `BankStatementAnalyzer`

This is the minimum necessary change to make the file importable in a non-Flask environment. All class logic is byte-for-byte identical to the Flask version.

---

## 4. Key Decisions

### Copy analyzer.py — don't symlink

Option A (symlink): create `backend-v2/app/models/analyzer.py` as a symlink to `backend/app/models/analyzeModel.py`.

**Rejected.** The Flask file imports `from flask import jsonify` at module level. Even if only `BankStatementAnalyzer` is imported, Python executes the entire module — Flask would become a hard dependency of the FastAPI venv. It also means any Flask-side change (e.g. adding `jsonify` calls inside the class) could silently break the FastAPI import.

Option B (copy with minimal adaptation): strip 3 import lines and the `AnalyzeModel` wrapper class. This is what was done.

**Why not a shared package?** The right long-term solution is to extract the parsing engine into a third package (`core/`) depended on by both backends. Deferred to BSA-09 (full Flask cutover) — at that point there's only one backend and the question goes away.

### Keep Flask alive

The Flask backend (`backend/`) is untouched. It continues to serve port 5000. The FastAPI backend serves port 8000. This gives a side-by-side comparison window: send the same file to both and diff the JSON. Flask is decommissioned only after parity is confirmed (BSA-09).

### to_thread not Celery

For this scale (single user, files typically < 5 MB, parsing < 2 seconds), Celery is overkill. `asyncio.to_thread` is enough — it keeps the event loop free without introducing Redis, a worker process, and a task queue.

Celery becomes the right answer if: (a) files routinely take > 10 seconds, (b) we need job-status polling, or (c) we want to retry failed parses. None of these are true yet. See `tech-debt.md` TD-007 if that changes.

---

## 5. What to Watch Out For

### RULE: every sync call in an async route must be in to_thread

If you add any pandas, pdfplumber, or other blocking call inside an `async def` route handler without wrapping it in `asyncio.to_thread`, you silently re-introduce the blocking problem. FastAPI will not warn you — it will just stall the event loop.

**Bad:**
```python
@router.post("/api/analyze/bank/statement")
async def analyze_statement(file: UploadFile = File(...)):
    result = BankStatementAnalyzer(path).extract_transactions()  # BLOCKS EVENT LOOP
    return JSONResponse(content=result)
```

**Good:**
```python
result = await asyncio.to_thread(
    lambda: BankStatementAnalyzer(str(file_path)).extract_transactions()
)
```

### StatementPeriod "from" field alias

`StatementPeriod` in `schemas.py` uses `from_date` as the Python attribute name with `alias="from"` because `from` is a Python keyword:

```python
class StatementPeriod(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_date: Optional[str] = Field(None, alias="from")
    to_date: Optional[str] = Field(None, alias="to")
```

The analyzer returns `{"from": "...", "to": "..."}` in the dict. When Pydantic serializes this model by alias, the JSON output uses `"from"` (correct). If you ever serialize by field name instead of alias, you'll get `"from_date"` — which breaks the frontend. Always use `model.model_dump(by_alias=True)` or `response_model_by_alias=True` on the route.

Currently `analyze.py` returns a raw `JSONResponse(content=result)` (the plain dict from the analyzer), so this Pydantic alias issue doesn't apply yet. It becomes relevant if we switch to `response_model=AnalyzeResponse`.

### File cleanup in finally

The `finally` block runs even if `file_path.write_bytes(content)` raises (e.g. disk full). In that case `file_path` exists but may be partial. The `if file_path.exists(): file_path.unlink()` guard handles this correctly.

### uploads/ is process-local

`UPLOAD_DIR = Path("uploads")` resolves relative to wherever `uvicorn` is launched from. If you run `uvicorn app.main:app` from `backend-v2/`, the uploads directory is `backend-v2/uploads/`. If launched from the project root, it would be `./uploads/`. The `UPLOAD_DIR.mkdir(exist_ok=True)` at module load time creates it wherever the process is started. Be consistent: always launch from `backend-v2/`.

---

## 6. What's Next

| Ticket | What |
|--------|------|
| BSA-09 | Full Flask cutover — update frontend VITE_API_URL to port 8000, decommission Flask |
| BSA-04 | LLM categorization — add Claude API call in the FastAPI route after parsing |
| TD-016 | Add integration tests for FastAPI endpoint (pytest + httpx AsyncClient) |
| BSA-10 | Parity validation — automated test that sends the same file to both backends and diffs the JSON shape |

The next highest-value task after this is **BSA-04** (LLM categorization) — that's the feature that justifies the FastAPI migration and requires the streaming/async foundation built here.
