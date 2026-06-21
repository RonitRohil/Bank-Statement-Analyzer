# Sprint-05 Plan

**Sprint dates:** 2026-07-05 → 2026-07-19 (2 weeks)  
**Capacity:** Moderate — evenings + weekends (~12 hours)  
**Backend:** FastAPI (`backend/`) only.

---

## Sprint Goal

**Build the longitudinal intelligence layer on top of Sprint-04's persistence foundation.**

Sprint-04 made the product stateful — data lives in SQLite. Sprint-05's job is to make that stored data *useful*: a history view, month-over-month comparison, cross-statement recurring detection, and the missing `GET /api/statements/{id}/transactions` endpoint that all of these need. On the structural side, Sprint-05 retires the monolithic analyzer class — a one-time cost that unlocks every future parser extension.

By end of sprint: a user can upload January, February, and March statements and see a month-over-month chart showing how spending changed. Recurring subscriptions detected across statements are flagged with cross-statement confidence. The analyzer is split into four focused modules.

---

## Theme: "Make the stored data earn its keep"

Sprint-04 proved the database decision was right. Sprint-05 proves the feature decision was right. Month-over-month comparison is the single most-requested longitudinal feature — it's also the clearest signal that the project has grown from a one-shot parser into a financial record.

---

## P0 — Must Ship

### Housekeeping block (first commit, ~45 min)

| Ticket | Fix | Est. |
|--------|-----|------|
| CR-S4-02 | `GET /api/statements/{id}/transactions` endpoint (blocks history UI) | 15 min |
| CR-S4-01 | Pagination on `GET /api/statements` (`limit`/`offset` query params) | 10 min |
| CR-S4-05 | Sanitize export `filename` param in `Content-Disposition` header | 5 min |
| CR-S4-03 | Document `CorrectionDB` fingerprint format in `crud.py` comment | 5 min |

These are low-effort CR findings from Sprint-04 that should be the first commit of the sprint.

### BSA-17 — Month-over-month comparison

**Prompt:** `docs/prompts/sprint-05/02-mom-comparison.md`  
**Est.:** 4–5h  
**Gated on:** BSA-19 (persistence ✅), CR-S4-02 (`GET .../transactions` endpoint — see housekeeping above)

**What it does:** For a given account number, pull all stored statements and aggregate transactions by calendar month. Return a `monthly_summary` array ordered by month. Surface this in the frontend as a month-over-month bar/line chart.

**Backend:**
- New endpoint: `GET /api/statements/compare?account_number=XXXX`
- Queries all `StatementDB` rows for the account, fetches their transactions from `TransactionDB`
- Groups by `YYYY-MM` (from `transaction_date`), computes per-month: income, expenses, net, top categories, top merchants
- Returns `{"months": [{"month": "2026-06", "income": ..., "expenses": ..., "net": ..., "top_category": "...", "delta_expenses": ...}]}`
- `delta_expenses`: % change vs. previous month (null for first month)

**Frontend:**
- New `MonthlyComparison.tsx` component
- Recharts `ComposedChart` with bars (income/expense) and a line (net)
- Month selector: user picks which stored account to compare (dropdown from `GET /api/statements` list)
- Renders in `App.tsx` below the main dashboard, only when `persistedStatements.length >= 2`

**Definition of done:**
- Upload 2+ statements from different months → chart shows both bars
- Single statement → chart renders gracefully with one data point (no crash)
- `pytest` green with at least 3 new tests for the compare endpoint

### TD-042 — `GET /api/statements/{id}/transactions` → typed response

(Covered by CR-S4-02 housekeeping. Promote to a named ticket for the tech-debt register.)

---

## P1 — Ship if Capacity Allows

### BSA-07-full — Cross-statement recurring detection

**Prompt:** `docs/prompts/sprint-05/03-cross-statement-recurring.md`  
**Est.:** 2–3h  
**Gated on:** BSA-19 (✅), `GET /api/statements/{id}/transactions` (✅ from housekeeping)

BSA-07 lite detects recurring merchants within a single statement. BSA-07-full compares `recurring_candidates` across statements for the same account. A merchant that appears recurring in ≥2 statements is a high-confidence subscription.

**Backend:**
- New `detect_cross_statement_recurring(account_number, session)` in `crud.py` or a new `app/services/recurring.py`
- Groups stored statements by `account_number`, collects `recurring_candidates` from each (stored in a new `recurring_candidates` JSON column on `StatementDB`, or re-derived on query)
- Returns merchants recurring in ≥2 of the last 3 statements as `confirmed_recurring` with average amount, month count, and last-seen date

**Frontend:**
- Extend `MerchantInsights.tsx` or add a new `SubscriptionsCard.tsx`
- Shows confirmed recurring subscriptions with monthly cost estimate

### TD-007/008 — Split `BankStatementAnalyzer` into focused modules

**Prompt:** `docs/prompts/sprint-05/04-analyzer-split.md`  
**Est.:** 3–4h  
**Gated on:** None (can be done in parallel with other items)

`BankStatementAnalyzer` is ~1,300 lines. Before adding more parsers (OCR, new bank formats), extract focused modules:

```
backend/app/
    parsers/
        excel_parser.py     ← _process_excel_csv() + _detect_header_row()
        pdf_parser.py       ← _process_pdf_transactions() + _looks_like_header()
    enrichers/
        narration_enricher.py   ← analyze_narration_details() + find_column()
    scorers/
        confidence_scorer.py    ← calculate_confidence_score()
    models/
        analyzer.py         ← BankStatementAnalyzer (now thin orchestrator, <200 lines)
                            ← TransactionPatternTrainer (stays here)
```

`BankStatementAnalyzer` becomes a thin orchestrator that imports and calls the focused modules. External API (import paths, behavior) stays unchanged. All 38 existing tests must pass.

**Definition of done:**
- `pytest` fully green — no test changes needed, only import paths inside `analyzer.py`
- `analyzer.py` < 300 lines
- Each new module has its own docstring explaining its responsibility

---

## P2 — Backlog (Sprint-06+)

| Ticket | Description | Gated on |
|--------|-------------|----------|
| BSA-06 | Natural-language Q&A over transaction history | Persistence (✅) + full history API |
| BSA-16 | Category-correction learning loop | `corrections` table (✅ in schema) |
| TD-018 | `TransactionTable` virtualization (`@tanstack/react-virtual`) | Before history inflates row counts significantly |
| TD-019 | Docker + docker-compose | Unblocked; defer until architecture settles |
| TD-023 | Magic-byte upload validation | None |
| TD-025 | `transaction_reference` regex too greedy | None |
| TD-026 | Confidence penalizes balance-less formats unconditionally | None |
| BSA-20 | Statement history UI + reload from DB | Sprint-05 history API |
| BSA-21 | Budget/alert thresholds | Sprint-05 MoM + category persistence |

---

## Architecture Decisions Needed This Sprint

| Decision | Recommendation |
|----------|---------------|
| Where to store `recurring_candidates` for BSA-07-full | JSON column on `StatementDB` (add in new Alembic migration) vs. re-derive on query. Storing avoids re-parsing; query is always fresh. Recommend storing — avoids coupling the compare endpoint to the parser. |
| Monthly comparison endpoint: GET vs. POST | `GET /api/statements/compare?account_number=...` is cleaner for a read-only query. No body needed. |
| Frontend state management for history | Continue with prop drilling for now (`App.tsx` holds the statement list). Global state (Zustand, Context) is premature until the history view proves complex. |
| Alembic migration for BSA-07-full | Add `recurring_candidates_json: Optional[str]` to `StatementDB` in a new migration. Keep migrations in `backend/alembic/versions/`. |

---

## Capacity Planning

| Work | Est. | Priority |
|------|------|----------|
| Housekeeping (CR-S4-01/02/03/05) | 45 min | P0 |
| BSA-17 month-over-month backend | 2–3h | P0 |
| BSA-17 month-over-month frontend | 1–2h | P0 |
| BSA-07-full cross-statement recurring | 2–3h | P1 |
| TD-007/008 analyzer split | 3–4h | P1 |
| **P0 total** | **~4–5h** | |
| **Total (all P0+P1)** | **~9–13h** | |

**Plan P0 only (~5h).** BSA-07-full is the first pull-forward. TD-007/008 is the second — do it if BSA-07-full finishes early.

---

## Definition of Done

- **CR-S4-02:** `GET /api/statements/{id}/transactions` returns typed transaction list; 404 on unknown ID.
- **CR-S4-01:** `GET /api/statements?limit=20&offset=0` works; default `limit=20`.
- **BSA-17:** Upload 2 statements from different months → `GET /api/statements/compare?account_number=...` returns 2 monthly rows with income/expense/net; `MonthlyComparison.tsx` renders a chart; `pytest` green with ≥3 new tests.
- **BSA-07-full (if shipped):** A merchant appearing as `recurring_candidate` in 2 out of the last 3 statements for an account appears in `confirmed_recurring`; tested with a 2-statement fixture.
- **TD-007/008 (if shipped):** `pytest` fully green with no test changes; `analyzer.py` < 300 lines.

---

## Key Risks

| Risk | Mitigation |
|------|-----------|
| Month-over-month comparison is useless without overlapping account numbers | `StatementDB.account_number` is extracted by regex from the statement text. If the extractor missed the number, compare returns no data. Add a fallback: allow compare by `bank_name` when `account_number` is null. |
| Analyzer split breaks an import path | The split must be purely internal — `BankStatementAnalyzer` stays importable from `app.models.analyzer`. Run the full test suite after each extract step, not at the end. |
| TD-007/008 consuming the sprint | Timebox to 4 hours. If blocked, defer to Sprint-06 — the monolith works, it's just hard to extend. |
| History UI pulling large datasets | `GET /api/statements/{id}/transactions` could return 1,000+ rows. Add the `limit`/`offset` pagination to this endpoint too (not just the list endpoint). |

---

## Claude Code Prompts

In `docs/prompts/sprint-05/`:

| File | Purpose |
|------|---------|
| `00-overview.md` | Sprint context + sequencing for Claude Code |
| `01-housekeeping.md` | CR-S4-01/02/03/05 — pagination, missing endpoint, sanitization |
| `02-mom-comparison.md` | BSA-17 — month-over-month compare endpoint + frontend chart |
| `03-cross-statement-recurring.md` | BSA-07-full — cross-statement recurring detection |
| `04-analyzer-split.md` | TD-007/008 — split monolithic analyzer into focused modules |

---

## Upcoming Sprints — Rolling Roadmap

### Sprint-06 — "Conversational + Hardening"

Natural-language Q&A over stored history (BSA-06). Category-correction learning loop (BSA-16 — uses `corrections` table from BSA-19). Parser hardening: magic-byte validation (TD-023), table virtualization (TD-018). Statement history UI with reload from DB (BSA-20).

### Sprint-07 — "Production Readiness"

Docker + docker-compose (TD-019). Budget/alert thresholds (BSA-21). `transaction_reference` regex fix (TD-025). Confidence scorer improvements (TD-026). OCR spike for scanned PDFs if demand is real.

### Continuous (every sprint)

- One architecture tech-debt item retired per sprint.
- Study doc + changelog updated at close (mandatory per `CLAUDE.md`).
- Tests for every new feature.

---

_Architecture: `docs/adr-002-persistence.md` · Tech debt: `docs/tech-debt.md` · Previous sprint: `docs/sprint-04-plan.md` · Feature brainstorm: `docs/feature-brainstorm.md`_
