# Requirements — Bank Statement Analyzer

**Status:** Living document — update whenever requirements change  
**Last updated:** 2026-05-29

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

### Non-Functional
- [x] Supports Indian banking narration formats (UPI structured, IMPS, NEFT, RTGS, BBPS)
- [x] Handles malformed/missing columns gracefully
- [x] Frontend error boundaries — one section crash doesn't kill the page

---

## Planned Requirements (v2 — in sprint planning)

### Architecture
- [ ] Migrate backend from Flask to FastAPI (ADR-001)
- [ ] Files deleted after analysis (privacy, disk safety) ← **SHIPPED 2026-05-29**
- [ ] File size limit (20 MB) + MIME type validation ← **SHIPPED 2026-05-29**
- [ ] Async job processing for large files (Celery + Redis)
- [ ] Health check endpoint `GET /api/health`

### ML/AI Features (from ml-ai-brainstorm.md)
- [ ] LLM categorization fallback — Claude Haiku for null-category narrations
- [ ] Automated financial summary report (natural language)
- [ ] Natural language Q&A (`POST /api/chat`)
- [ ] Recurring transaction detection (stats-based)
- [ ] Anomaly detection (IsolationForest)
- [ ] TF-IDF + Logistic Regression categorizer (Phase 2)

### Frontend
- [ ] Transaction table pagination or virtual scroll (performance at 1000+ rows)
- [ ] Persist last analysis in sessionStorage (survives page refresh)
- [ ] LLM chat interface for Q&A

### Quality
- [ ] Unit tests: `parse_amount`, `normalize_date`, `analyze_narration_details`
- [ ] Integration test: `/api/analyze/bank/statement` with fixture files
- [ ] Frontend tests: FileUpload, TransactionTable

### Infrastructure
- [ ] Dockerfile + docker-compose
- [ ] gunicorn for production
- [ ] Structured logging with request IDs

---

## Requirement Changes Log

| Date | Change | Reason | Decision |
|------|--------|--------|----------|
| 2026-05-29 | Files must be deleted after analysis | Privacy + disk safety | Implemented in controller `finally` block |
| 2026-05-29 | File size limit 20 MB | Security — prevent DoS via huge uploads | Config.MAX_UPLOAD_SIZE |
| 2026-05-29 | CORS default tightened to localhost:3000 | Wildcard CORS is unsafe | Config.CORS_URLS default changed |
| 2026-05-29 | Migrate to FastAPI | LLM streaming, Pydantic, auto-docs | ADR-001 accepted |
| 2026-05-29 | Remove scikit-learn from requirements | Unused dependency, 120 MB dead weight | Removed; will re-add when ML features are built |
