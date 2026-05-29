# Sprint 01 Plan

**Sprint dates:** 2026-05-29 → 2026-06-12 (2 weeks)  
**Capacity:** Moderate — evenings + weekends (~10 hours available)  
**Projects:** Bank Statement Analyzer · FinanceAssistant · Job Prep

---

## Sprint Goal

Ship the Bank Statement Analyzer critical fixes (already done ✅), begin the FastAPI migration scaffold, and make meaningful progress on FinanceAssistant Phase 2 — while keeping Job Prep continuous work flowing.

---

## Capacity Split

| Project | Hours | Rationale |
|---------|-------|-----------|
| Bank Statement Analyzer | 4h | FastAPI scaffold + one LLM quick win |
| FinanceAssistant Phase 2 | 4h | Extensive — needs focused effort |
| Job Prep | 2h | Continuous, lower intensity |

---

## P0 — Must Ship This Sprint

### Bank Statement Analyzer

| # | Task | Est. | Notes |
|---|------|------|-------|
| BSA-01 | ✅ Fix all critical tech debt (TD-001 → TD-011) | Done | Shipped in this session |
| BSA-02 | Scaffold FastAPI backend (`backend-v2/`) | 2h | Create FastAPI app, health endpoint, Pydantic models for Transaction + AccountInfo. No business logic yet. |
| BSA-03 | Port `POST /api/analyze/bank/statement` to FastAPI | 1.5h | Wrap `BankStatementAnalyzer` in `asyncio.to_thread()`. Validate parity with test CSV. |

### FinanceAssistant

| # | Task | Est. | Notes |
|---|------|------|-------|
| FA-01 | Identify and document Phase 2 scope | 0.5h | Map out what Phase 2 covers — features, endpoints, data model changes |
| FA-02 | Phase 2 top priority feature (TBD) | 3h | Most impactful unblocked Phase 2 item |

### Job Prep

| # | Task | Est. | Notes |
|---|------|------|-------|
| JP-01 | Continuous ongoing work | 2h | Keep momentum — specific tasks per your prep schedule |

---

## P1 — Ship if Capacity Allows

| # | Project | Task | Est. |
|---|---------|------|------|
| BSA-04 | BSA | LLM categorization fallback (Claude Haiku for null-category narrations) | 1h |
| BSA-05 | BSA | Automated financial summary endpoint | 1h |
| FA-03 | FA | Phase 2 second priority feature | 2h |

---

## P2 — Backlog (next sprint)

| # | Project | Task |
|---|---------|------|
| BSA-06 | BSA | Natural language Q&A endpoint (`POST /api/chat`) |
| BSA-07 | BSA | Recurring transaction detection (stats-based) |
| BSA-08 | BSA | Anomaly detection (IsolationForest) |
| BSA-09 | BSA | Full Flask → FastAPI cutover + deprecate Flask |
| BSA-10 | BSA | Write pytest unit tests for `parse_amount`, `normalize_date`, `analyze_narration_details` |
| FA-04 | FA | Phase 2 remaining features |
| JP-02 | JP | TBD per prep timeline |

---

## Definition of Done

- **BSA-02/03:** FastAPI app boots, health endpoint returns 200, `/api/analyze/bank/statement` accepts same CSV and returns same JSON shape as Flask version
- **FA-01:** Written scope doc or feature list for Phase 2
- **FA-02:** Feature merged and working end-to-end
- **JP-01:** Prep sessions completed per schedule

---

## Key Dependencies & Risks

| Risk | Mitigation |
|------|-----------|
| FastAPI migration takes longer than estimated | Keep Flask running in parallel — no hard cutover this sprint |
| FinanceAssistant Phase 2 is more complex than expected | FA-01 scoping task should surface this early |
| LLM API costs run up | Use Claude Haiku/GPT-4o-mini; add per-request cost logging |
| Async bugs (blocking the event loop) | Wrap all pandas/pdfplumber calls in `asyncio.to_thread()` without exception |

---

## Architecture Decisions Made This Session

| Decision | Status |
|----------|--------|
| Migrate to FastAPI | ✅ Decided — see `adr-001-flask-vs-fastapi.md` |
| LLM strategy: Claude Haiku for quick wins, ML classifiers for Phase 2 | ✅ See `ml-ai-brainstorm.md` |
| Keep regex + ML as primary, LLM as fallback/enrichment | ✅ Hybrid approach recommended |

---

## Files Created This Session

| File | Purpose |
|------|---------|
| `docs/architecture.md` | Architecture overview |
| `docs/system-design.md` | System design recommendations |
| `docs/tech-debt.md` | 20-item prioritized tech debt backlog |
| `docs/code-review.md` | Line-level code review findings |
| `docs/adr-001-flask-vs-fastapi.md` | Architecture decision record |
| `docs/ml-ai-brainstorm.md` | ML/AI/LLM feature roadmap |
| `docs/sprint-01-plan.md` | This file |
| `backend/.env.example` | Environment variable template |
| `frontend/.env.example` | Frontend env template |

---

## Changes Applied This Session (all committed-ready)

| File | Change |
|------|--------|
| `backend/requirements.txt` | Fixed UTF-16 encoding → clean UTF-8 minimal deps |
| `backend/app/config/config.py` | Added `INTEGRATION_URL`, `INTEGRATION_AUTH`, `MAX_UPLOAD_SIZE` |
| `backend/app/__init__.py` | Added `logging.basicConfig` |
| `backend/run.py` | `debug=True` → env-controlled |
| `backend/app/controllers/analyzeController.py` | File cleanup (finally block), size/ext validation, UUID filenames |
| `backend/app/models/analyzeModel.py` | Removed 4 dead classes, removed sklearn imports, fixed PDF confidence_score gap, fixed `and`→`or` bug, fixed double assignment, removed dead vars, all `print()` → `logger.*` |
| `frontend/services/api.ts` | API URL uses `VITE_API_URL` env var |
