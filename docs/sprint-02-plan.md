# Sprint-02 Plan

**Sprint dates:** 2026-06-13 → 2026-06-27 (2 weeks)  
**Capacity:** Moderate — evenings + weekends (~10 hours)  
**Backend:** FastAPI (`backend-v2/`) — Flask stays alive until BSA-09 cutover this sprint

---

## Sprint Goal

Cut over to FastAPI, ship the first LLM feature (categorization fallback), and give users a real financial summary. By end of sprint, Flask is decommissioned and every new feature runs on FastAPI.

---

## Brainstorm: What's Newly Possible Now That We Have FastAPI

Sprint-01 built the foundation. Sprint-02 is where we collect on the investment:

**Newly unlocked by ASGI:**
- LLM streaming via SSE — real-time "thinking" progress in the UI
- Background tasks (FastAPI `BackgroundTasks`) — fire-and-forget operations like sending emails, writing history
- WebSocket — live progress bar during parsing (no polling needed)
- `asyncio.to_thread` everywhere — parallel parsing of multiple files without Celery

**What the data enables that we haven't touched yet:**
- Spending summary per category (math-only, no LLM, high user value)
- Recurring transaction detection (regex + stats, no ML needed yet)
- Top merchants by spend (already computed in `merchant_insights` — just needs a better endpoint)
- Month-over-month trend line (need history store — Sprint-03)

**What's blocking user value right now:**
- Frontend still points at Flask (port 5000). FastAPI is live but users don't see it.
- BSA-09 is the gateway. Until it's done, BSA-04 (LLM) has no user-facing path.

---

## P0 — Must Ship This Sprint

### FastAPI Housekeeping (Day 1 — ~30 min)
Fix four 1-liner tech debt items before writing any new code.

| Ticket | Fix |
|--------|-----|
| TD-028 | `reload=True` → env-controlled in `backend-v2/run.py` |
| TD-029 | Remove `import requests` from `analyzer.py` + `requests` from requirements |
| TD-030 | CORS wildcards → explicit `allow_methods`, `allow_headers` |
| TD-032 | `UPLOAD_DIR = Path("uploads")` → file-relative path |

**Prompt file:** `docs/prompts/sprint-02/01-fastapi-housekeeping.md`

---

### BSA-10: FastAPI Integration Tests (~3-4 hours)
Tests are the prerequisite for BSA-09. We cannot cut over to FastAPI until we can prove parity.

**What's needed:**
- `backend-v2/tests/test_health.py` — GET `/api/health` returns 200 + correct JSON
- `backend-v2/tests/test_analyze.py` — POST with fixture CSV and PDF; assert response shape
- Parity test — same file → both backends → same JSON shape (not values)
- Tools: `httpx.AsyncClient` + `pytest-asyncio`

**Prompt file:** `docs/prompts/sprint-02/02-fastapi-tests.md`

---

### BSA-09: Full Flask → FastAPI Cutover (~1 hour)
After tests pass, cut the frontend over to port 8000 and decommission Flask.

**What changes:**
- `frontend/.env` / `.env.local`: `VITE_API_URL=http://localhost:8000`
- `CLAUDE.md` — update port references
- `docs/architecture.md` — mark Flask as decommissioned
- `backend/run.py` — add deprecation warning, keep alive for 1 more sprint just in case

**Prompt file:** `docs/prompts/sprint-02/03-flask-cutover.md`

---

### BSA-04: LLM Categorization Fallback (~2-3 hours)
The feature that justifies the FastAPI migration. When the regex narration analyzer returns `category=[]`, call Claude Haiku to classify the transaction.

**Design:**
- New function `async def enrich_with_llm(transactions: list) -> list` in `backend-v2/app/services/llm_enricher.py`
- Called from `analyze.py` after `extract_transactions()` runs, before building the response
- Only called for transactions where `category == []` (reduces API cost)
- Prompt: structured JSON input, ask for category + merchant from narration text
- Fallback: if LLM call fails, return transaction as-is (no blocking)
- Add `ANTHROPIC_API_KEY` to `backend-v2/.env.example` and `settings.py`
- Add `anthropic==0.52.0` to `backend-v2/requirements.txt`

**Prompt file:** `docs/prompts/sprint-02/04-llm-categorization.md`

---

## P1 — Ship If Capacity Allows

### BSA-05: Financial Summary Endpoint (~1.5 hours)
New endpoint: `POST /api/analyze/bank/summary`  
Input: `{"transactions": [...]}` (the array from the analyze response)  
Output: total income, total expenses, net, per-category spend, top 5 merchants, date range

No new ML or LLM needed — pure Python math on the transactions array. Gives users an instant "what's happening with my money" view.

**Prompt file:** `docs/prompts/sprint-02/05-financial-summary.md`

---

### TD-021: Multi-page PDF Row Stitching (~3 hours)
Silent data loss bug — the single most impactful correctness fix.  
When a PDF table spans pages without repeating headers, the first data row of each continuation page is consumed as column names.

**Prompt file:** `docs/prompts/sprint-02/06-multipage-pdf.md`

---

## P2 — Backlog (Sprint-03)

| Ticket | Description | Why it's not Sprint-02 |
|--------|-------------|----------------------|
| BSA-06 | Natural language Q&A (`POST /api/chat`) | Needs history store (Sprint-03) |
| BSA-07 | Recurring transaction detection | Needs multi-statement data |
| BSA-08 | Anomaly detection (IsolationForest) | Needs training data from history |
| TD-007 | Split monolithic analyzer | Best paired with BSA-09 cutover |
| BSA-11 | SSE streaming progress during analysis | Nice UX; FastAPI makes it easy |
| BSA-12 | Frontend: filters, search, date picker | UI polish sprint |
| BSA-13 | Export transactions as CSV | Frontend-only, quick win |
| BSA-14 | Docker + docker-compose | After architecture stabilizes |

---

## New Ideas from Brainstorm

These aren't on the backlog yet but are worth tracking:

**1. Streaming parse progress (BSA-11)**  
FastAPI SSE makes this trivial. As the analyzer processes pages, stream progress events:
```
data: {"stage":"parsing","progress":0.2,"pages":2}
data: {"stage":"enriching","progress":0.6,"transactions":150}
data: {"stage":"done","result":{...}}
```
Frontend shows a real progress bar instead of a spinner. High perceived-performance win.

**2. Smart insights (no LLM needed) (BSA-15)**  
After parsing, compute simple statistical insights:
- "Your top spending category is Food & Dining (32%)"
- "You have 8 potential recurring transactions"
- "PAYTM MALL is your most frequent merchant (12 transactions)"
These are all derivable from the existing `merchant_insights` and `transactions` arrays — no new endpoint needed, just a new key in the response.

**3. Inline category correction (BSA-16)**  
Let users correct wrong categories in the frontend table. Store corrections in `localStorage` for now (pre-history-store). This creates training data for the future ML classifier.

**4. Multi-statement comparison (BSA-17)**  
Upload Jan + Feb + Mar statements, get a side-by-side month comparison. FastAPI's async model makes parallel processing natural. Needs a history store to be persistent, but a stateless "compare these three" endpoint is possible without it.

---

## Definition of Done

- **TD-028-032:** All four fixes in one commit; passes tests
- **BSA-10:** `pytest backend-v2/tests/` passes; parity test shows matching JSON shapes
- **BSA-09:** Frontend loads at `localhost:5173` and hits FastAPI on port 8000; Flask can be stopped without breaking anything
- **BSA-04:** Uploading a statement with unknown merchants shows LLM-categorized results; `category` field is never empty for common transactions
- **BSA-05:** `POST /api/analyze/bank/summary` returns correct totals for a known fixture

---

## Architecture Decisions Needed This Sprint

| Decision | Context |
|----------|---------|
| LLM call sync vs async | Claude API has an async client — use it or wrap sync in `to_thread`? Use async (`anthropic.AsyncAnthropic`) |
| LLM per-transaction vs batch | Per-transaction is simple but expensive. Batch in one prompt: cheaper, but needs careful output parsing. Recommend batch (10 at a time) |
| Summary endpoint vs summary in analyze response | Endpoint is more flexible for frontend. But adds a second round-trip. Add as an optional `?include_summary=true` query param on the existing endpoint for Sprint-02. |

---

## Key Risks

| Risk | Mitigation |
|------|-----------|
| LLM API costs spike during testing | Use Haiku (cheapest), add per-request token logging |
| Parity test reveals Flask/FastAPI shape differences | Catch before BSA-09 cutover — that's the point of BSA-10 |
| Multi-page PDF fix introduces regressions | Don't pair with BSA-09 — keep Flask alive until tested |

---

*Prompt files: `docs/prompts/sprint-02/`*  
*Previous sprint: `docs/sprint-01-plan.md`*  
*Tech debt: `docs/tech-debt.md`*
