# Requirements — Bank Statement Analyzer

**Status:** Living document — update whenever requirements change
**Last updated:** 2026-06-20

---

## Product Vision

A personal finance tool that turns raw bank statements (any format) into actionable spending insights. Fast, accurate, explainable.

---

## Current Requirements (v1 — shipped)

### Functional

- [x] Upload bank statement (PDF, Excel .xlsx/.xls, CSV)
- [x] Parse transactions: date, amount (credit/debit), narration, balance
- [x] Detect payment method (UPI, IMPS, NEFT, RTGS, CARD, CHEQUE, ATM, etc.)
- [x] Extract merchant name from narration
- [x] Categorize transactions (E-COMMERCE, FOOD_DELIVERY, TRAVEL, etc.)
- [x] Extract account metadata (account number, holder name, bank, IFSC, statement period)
- [x] Confidence score per transaction and overall
- [x] Merchant insights (count, avg/median/std amount, first/last seen, common days)
- [x] Interactive dashboard: account overview, charts, merchant table, transaction list
- [x] LLM categorization fallback via Ollama (BSA-04, Sprint-02)
- [x] Financial summary endpoint `POST /api/analyze/bank/summary` (BSA-05, Sprint-02)

### Non-Functional

- [x] Supports Indian banking narration formats (UPI structured, IMPS, NEFT, RTGS, BBPS)
- [x] Handles malformed/missing columns gracefully
- [x] Frontend error boundaries — one section crash doesn't kill the page
- [x] FastAPI on port 8000 — async, Pydantic v2, Swagger UI at `/docs`
- [x] Health check endpoint `GET /api/health`
- [x] File size limit (20 MB) + extension validation
- [x] Uploaded files deleted after every request (privacy, disk safety)
- [x] CI workflow: pytest + requirements.txt encoding guard (BSA-18, Sprint-03)

---

## Planned Requirements (v2 — in sprint planning)

### Architecture

- [ ] Async job processing for large files (Celery + Redis)

### ML/AI Features (from ml-ai-brainstorm.md)

- [ ] LLM enrichment UI — surface `llm_enriched` flag and summary endpoint in the dashboard (TD-038)
- [ ] Automated financial summary report (natural language)
- [ ] Natural language Q&A (`POST /api/chat`)
- [ ] Recurring transaction detection (stats-based)
- [ ] Anomaly detection (IsolationForest)
- [ ] TF-IDF + Logistic Regression categorizer (Phase 2)
- [ ] Bound LLM enrichment — global timeout + batch cap (TD-035)

### Frontend

- [ ] Transaction table pagination or virtual scroll (performance at 1000+ rows)
- [ ] Persist last analysis in sessionStorage (survives page refresh)
- [ ] LLM chat interface for Q&A
- [ ] Frontend test suite (Vitest + React Testing Library)

### Infrastructure

- [ ] Dockerfile + docker-compose
- [ ] uvicorn via gunicorn workers for production
- [ ] Structured logging with request IDs

---

## Requirement Changes Log

| Date       | Change                                   | Reason                                                            | Decision                                                |
| ---------- | ---------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------- |
| 2026-06-20 | Flask backend removed (BSA-18)           | Rollback window expired; two backends = guaranteed drift (TD-007) | Deleted `backend/`; FastAPI is the canonical backend    |
| 2026-06-20 | CI workflow added (BSA-18)               | No CI existed; TD-001 (UTF-16 encoding) needed a guard            | `.github/workflows/test.yml`: pytest + encoding guard   |
| 2026-06-20 | LLM enricher index bug fixed (TD-033)    | BSA-04 was silently no-oping since Sprint-02                      | Fixed double-index; aggregates recomputed post-enrich   |
| 2026-06-20 | Summary endpoint typed (TD-036)          | Raw dict input → 500 on bad amounts                               | Retyped with `Transaction` schema; bad input → 422      |
| 2026-06-20 | API base URL centralized (TD-037)        | Stale `:5000` references in error messages post-cutover           | `API_BASE` exported from `api.ts`; fallback → port 8000 |
| 2026-05-29 | Files must be deleted after analysis     | Privacy + disk safety                                             | Implemented in controller `finally` block               |
| 2026-05-29 | File size limit 20 MB                    | Security — prevent DoS via huge uploads                           | `MAX_UPLOAD_SIZE_MB` in pydantic-settings               |
| 2026-05-29 | CORS default tightened to localhost:3000 | Wildcard CORS is unsafe                                           | `cors_origins` setting default changed                  |
| 2026-05-29 | Migrate to FastAPI                       | LLM streaming, Pydantic, auto-docs                                | ADR-001 accepted                                        |
| 2026-05-29 | Remove scikit-learn from requirements    | Unused dependency, 120 MB dead weight                             | Removed; will re-add when ML features are built         |
