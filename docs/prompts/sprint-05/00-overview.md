# Sprint-05 Overview — Longitudinal Intelligence v1

**For:** Claude Code  
**Date:** 2026-06-21  
**Sprint plan:** `docs/sprint-05-plan.md`  
**Previous sprint:** `docs/study/sprint-04-learnings.md`

---

## What Sprint-05 Is

Sprint-04 shipped persistence (BSA-19). Now we build on top of it. The goal: make stored financial data useful — month-over-month comparison, cross-statement recurring detection, and the structural analyzer split that unlocks future parser extensions.

The stateless upload path is unchanged. We're adding longitudinal endpoints that query what's been stored.

---

## The Repository State You're Starting From

```
backend/
    app/
        db/
            models.py      ← StatementDB, TransactionDB, CorrectionDB (Sprint-04)
            database.py    ← engine, get_session, create_db_and_tables
            crud.py        ← hash_file, find_statement_by_hash, save_statement
        routers/
            analyze.py     ← POST /api/analyze/bank/statement (persist=true flag)
            statements.py  ← GET /api/statements (all statements, no pagination yet)
            export.py      ← POST /api/export/transactions
            summary.py     ← POST /api/analyze/bank/summary
            health.py      ← GET /api/health
        services/
            insights.py    ← generate_insights() + detect_recurring()
            llm_enricher.py
            categories.py
        models/
            analyzer.py    ← BankStatementAnalyzer + TransactionPatternTrainer (~1,300 lines)
            schemas.py     ← Pydantic v2 models
        config/settings.py
        main.py
    alembic/versions/      ← 1 migration (9670b8f28c89 — creates 3 tables)
    tests/                 ← ~38 tests passing
frontend/
    components/
        TransactionTable.tsx  ← CSV/Excel download buttons
        MerchantInsights.tsx  ← ↻ pill on recurring merchants
        SpendingSummary.tsx
        InsightsStrip.tsx
        ...
```

---

## Prompt Sequence

Run prompts in order. **Do not start the next prompt until the previous one is complete and tests pass.**

| Prompt | Ticket | Description |
|--------|--------|-------------|
| `01-housekeeping.md` | CR-S4-01/02/03/05 | Fix CR findings from Sprint-04 review — first commit |
| `02-mom-comparison.md` | BSA-17 | Month-over-month comparison endpoint + Recharts frontend |
| `03-cross-statement-recurring.md` | BSA-07-full | Cross-statement recurring detection (P1 — do if capacity) |
| `04-analyzer-split.md` | TD-007/008 | Split monolithic analyzer into focused modules (P1 — do if capacity) |

---

## Ground Rules for This Sprint

1. **Read before writing.** Read the relevant file(s) before editing. Understand what already exists.
2. **Tests first for new endpoints.** Every new backend endpoint gets tests in the corresponding `tests/test_*.py` file. New test file if the feature is distinct.
3. **Stateless path must stay unchanged.** Every new endpoint is additive. No change to how `POST /api/analyze/bank/statement` works without `persist=true`.
4. **Alembic for schema changes.** If adding a column to `StatementDB` or `TransactionDB` (e.g., `recurring_candidates_json`), create a new Alembic migration. Do not modify `9670b8f28c89`.
5. **Type everything.** No `list[dict[str, Any]]` in new route handlers. Define a Pydantic response model in `schemas.py` or inline in the router.
6. **Run `pytest` after each prompt before moving to the next.**

---

## Key Files to Read Before Starting

- `docs/sprint-05-plan.md` — full sprint design
- `docs/code-review.md` — Sprint-04 review findings (these are what prompt 01 fixes)
- `docs/adr-002-persistence.md` — the persistence design decisions
- `backend/app/db/models.py` — table schemas
- `backend/app/db/crud.py` — existing CRUD helpers
- `backend/app/routers/statements.py` — current endpoint (being extended)
