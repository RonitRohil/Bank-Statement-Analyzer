# ADR-001: Flask vs FastAPI for Backend Framework

**Status:** Proposed  
**Date:** 2026-05-29  
**Deciders:** Ronit Jain  
**Context project:** Bank Statement Analyzer

---

## Context

The current backend is Flask 3.1.2 — synchronous, single-threaded, running with one worker. The primary pain point identified in the system design review is that large PDF/Excel files block the entire Flask worker thread during parsing (which can take 5–30 seconds). This blocks all other requests.

We are also planning to add:
- ML/LLM-powered transaction categorization
- Async job processing for large files
- Potential WebSocket progress updates
- More endpoints as the app grows into a richer product

The question is whether to stay on Flask or migrate to FastAPI.

---

## Options Considered

### Option A: Stay on Flask + add async via Celery/RQ

Keep Flask as-is. Add Redis + Celery (or RQ) as a task queue. The upload endpoint returns a `job_id` immediately; a worker picks up the processing job.

| Dimension | Assessment |
|-----------|------------|
| Migration effort | None — no code rewrite |
| Async support | ✅ Via task queue (Celery/RQ), not native async |
| Performance (raw) | Moderate — WSGI, but sufficient with gunicorn workers |
| ML/LLM integration | ✅ Works fine — Celery workers can load heavy models |
| Type safety | ❌ No built-in request/response validation |
| API docs | ❌ Manual — no auto-generated OpenAPI |
| Team familiarity | ✅ Already using Flask |
| Ecosystem maturity | ✅ 15+ years, massive ecosystem |

**Pros:**
- Zero migration cost — every line of code stays
- Celery solves the blocking problem completely
- Flask is battle-tested; no surprise behaviors
- Works fine for this scale (1 user or small team)

**Cons:**
- No native `async/await` — adding it requires Quart or manual workarounds
- No built-in Pydantic validation — request parsing is manual
- No auto-generated OpenAPI/Swagger docs
- More verbose error handling

---

### Option B: Migrate to FastAPI

Rewrite the backend in FastAPI. All route handlers become async-capable. Pydantic models replace manual request parsing.

| Dimension | Assessment |
|-----------|------------|
| Migration effort | Medium — all routes + models need rewriting (~1–2 sprints) |
| Async support | ✅ Native `async/await` — built on Starlette (ASGI) |
| Performance (raw) | High — ASGI handles concurrent requests without blocking |
| ML/LLM integration | ✅ Excellent — async inference calls, streaming responses |
| Type safety | ✅ Pydantic v2 — request/response validation built in |
| API docs | ✅ Auto-generated Swagger UI at `/docs` |
| Team familiarity | 🟡 Requires learning Pydantic, Depends, lifespan |
| Ecosystem maturity | ✅ Production-proven; major orgs use it at scale |

**Pros:**
- Native async = no need for Celery for simple cases (background tasks built in)
- Pydantic eliminates manual validation code (a weakness in the current codebase)
- Auto-generated API docs are a significant developer experience win
- Better fit for LLM streaming responses (Server-Sent Events / streaming JSON)
- Faster path to adding WebSocket support

**Cons:**
- Real migration work — every route handler, all models need rewriting
- Pydantic v2 has a learning curve
- `async` pandas/pdfplumber operations still block the event loop unless run in a thread pool (must use `asyncio.to_thread()` or `run_in_executor()`)
- You can still have blocking bugs in async code if not careful

---

### Option C: Flask + Async via Quart (Flask-compatible ASGI)

Keep Flask syntax but switch to Quart as the ASGI runtime. Near-zero API changes.

| Dimension | Assessment |
|-----------|------------|
| Migration effort | Low — mostly drop-in replacement |
| Async support | ✅ Native async/await |
| Ecosystem | 🟡 Smaller than Flask or FastAPI |
| Pydantic / OpenAPI | ❌ No built-in |

**Assessment:** Not recommended — provides native async but without the type safety and DX wins of FastAPI. Best of neither world.

---

## Trade-off Analysis

The core tension is **migration cost vs. long-term DX and performance**.

**The blocking problem is real but solvable with Celery on Flask.** If this stays a small personal project or internal tool, Flask + Celery is 100% sufficient and costs nothing to implement.

**FastAPI becomes clearly the right choice if:**
1. LLM streaming responses are a requirement (SSE/WebSocket)
2. The API surface grows significantly (more endpoints, complex request schemas)
3. Multiple developers need to onboard — auto docs help a lot
4. You want to avoid managing Celery/Redis for the async problem

**The pdfplumber/pandas caveat:** Even in FastAPI, CPU-bound parsing must be wrapped in `asyncio.to_thread()` to avoid blocking the event loop. This is easy but must be done consistently. FastAPI doesn't magically make sync code async.

---

## Recommendation: **Migrate to FastAPI (Option B)**

**Reasoning:**

Given the planned ML/LLM features, FastAPI is the stronger long-term foundation:
- LLM streaming (token-by-token responses) requires SSE or WebSocket — FastAPI handles this naturally; Flask does not
- Pydantic models will eliminate a whole class of bugs that currently exist (the hardcoded response shapes with no validation)
- Auto OpenAPI docs are valuable for a project you might share or demo
- The migration is bounded — there are only ~3 routes and 3 model classes to port

**Migration path (low-risk, incremental):**
1. Add FastAPI alongside Flask — run both on different ports initially
2. Port one endpoint at a time, validate parity
3. Update frontend to point to FastAPI
4. Decommission Flask

This avoids a big-bang rewrite.

---

## Consequences

**What becomes easier:**
- Adding LLM streaming endpoints
- Request validation (Pydantic replaces ad-hoc checks)
- API documentation (auto-generated)
- Async LLM API calls without task queue overhead for simple operations

**What becomes harder:**
- CPU-bound parsing must explicitly use `asyncio.to_thread()` — easy to forget
- Team needs to learn Pydantic v2 dependency injection pattern
- Celery still needed for very large files or background jobs (not avoided entirely)

**What we'll need to revisit:**
- All response shapes should be Pydantic models (good forcing function to formalize the API contract)
- `analyzeController.py` logic moves into FastAPI route handlers or service layer
- CORS config moves to FastAPI middleware

---

## Action Items

1. [x] Create `backend-v2/` with FastAPI scaffold
2. [x] Define Pydantic models for `Transaction`, `AccountInfo`, `AnalysisResult` (mirror existing `types.ts`)
3. [x] Port `POST /api/analyze/bank/statement` to FastAPI — wrap `BankStatementAnalyzer` in `asyncio.to_thread()`
4. [x] Add `GET /api/health` endpoint
5. [ ] Validate parity with current Flask endpoint using same test files
6. [ ] Update frontend `VITE_API_URL` to point to FastAPI
7. [ ] Decommission Flask backend once parity confirmed
8. [ ] Add Celery + Redis for large file async processing (separate ticket)

---

*Related: `system-design.md` § Async Job Queue, `tech-debt.md` TD-007*
