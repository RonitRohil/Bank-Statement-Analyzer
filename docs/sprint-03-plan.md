# Sprint-03 Plan

**Sprint dates:** 2026-06-20 → 2026-07-04 (2 weeks)
**Capacity:** Moderate — evenings + weekends (~10 hours)
**Backend:** FastAPI (`backend-v2/`) only. **Flask is deleted this sprint.**

---

## Sprint Goal

**Finish Sprint-02, then make its value visible.** Sprint-02 shipped the plumbing for LLM categorization and a financial summary, but neither works end-to-end: the enricher silently no-ops (TD-033), and both features have no UI. Sprint-03's first job is to close that gap, not add scope. The second job is to make one architectural decision the project keeps deferring — **persistence** — and design the data model so Sprint-04 can build the longitudinal features that are the real product.

By end of sprint: a user uploads a statement and sees correctly AI-categorized transactions and a spending-summary card; Flask is gone; and there's a committed data-model design for history.

---

## Theme: "Don't start new things while old things are half-built."

See `docs/feature-brainstorm.md` Tier 1. The temptation is anomaly detection and chat. The discipline is to finish BSA-04/05 first.

---

## P0 — Must Ship (finish Sprint-02 + decommission Flask)

### Block A — Fast-follow fixes (the features must actually work)

| Ticket | Fix | Est. | Prompt |
|--------|-----|------|--------|
| TD-033 | LLM enricher index bug → map by global index + bounds check + **unit test** | 1h | `prompts/sprint-03/01-llm-enricher-fix.md` |
| TD-037 | Stale `localhost:5000` strings → centralize on `API_BASE` (default 8000) | 20m | `prompts/sprint-03/02-frontend-url-cleanup.md` |
| TD-036 | Type the summary endpoint input (reuse `Transaction`) + unit test | 30m | `prompts/sprint-03/03-summary-typing.md` |
| TD-034 | Enrich **before** computing `merchant_insights`/`confidence_summary` | 1–2h | `prompts/sprint-03/01-llm-enricher-fix.md` (same prompt) |
| TD-035 | Bound enrichment: global wall-clock budget + batch cap | 1–2h | `prompts/sprint-03/04-bound-enrichment.md` |
| CR-S2-08 | Unify category taxonomy (regex `FOOD_DELIVERY` vs LLM `Food & Dining`) | 1h | `prompts/sprint-03/04-bound-enrichment.md` (paired) |

### Block B — Decommission Flask (BSA-18)

Flask was kept one sprint as rollback. The FastAPI suite is green and the cutover held. Remove it.

| What | Detail | Prompt |
|------|--------|--------|
| Delete `backend/` | Remove the Flask app, its tests, `conftest.py` | `prompts/sprint-03/05-delete-flask.md` |
| Delete `test_parity.py` | Nothing left to compare against | same |
| Update docs | `CLAUDE.md`, `architecture.md`, `requirements.md` — drop the dual-backend framing | same |
| CI guard | Add `.github/workflows/test.yml` incl. the TD-001 encoding check | same |

---

## P1 — Make the Value Visible (ship if capacity allows)

### BSA-12 / TD-038 — Spending Summary card + AI badge (frontend)
Wire `POST /api/analyze/bank/summary` into the dashboard. New `SummarySummaryCard` showing income / expense / net / top categories. Add `llm_enriched` to `types.ts` and render an "AI" badge on enriched rows.
**Prompt:** `prompts/sprint-03/06-summary-frontend.md`
**Est.:** 3–4h

### BSA-15 — Smart Insights strip (stats, no LLM)
A row of plain-language callouts derived from the existing response. Highest perceived-intelligence-per-hour in the backlog.
**Prompt:** `prompts/sprint-03/07-smart-insights.md`
**Est.:** 3–4h

---

## P2 — Architectural Decision (design only this sprint)

### ADR-002 — Persistence layer
**Decide and document, don't necessarily build.** Recommendation (carried from Sprint-02 backlog + `feature-brainstorm.md`): **SQLite via SQLModel**. Design the data model (`statements`, `transactions`, `corrections`) and write the ADR. Implementation lands Sprint-04.
**Prompt:** `prompts/sprint-03/08-adr-persistence.md` (this is a *design* prompt — produces an ADR, not code)
**Est.:** 2h (writing + review)

---

## P3 — Backlog (Sprint-04+)

| Ticket | Description | Gated on |
|--------|-------------|----------|
| BSA-19 | Persistence implementation (SQLite/SQLModel) | ADR-002 |
| BSA-07 | True cross-statement recurring detection | Persistence |
| BSA-17 | Month-over-month comparison | Persistence + TD-024 dedup |
| BSA-06 | Natural-language Q&A | Persistence |
| BSA-16 | Category-correction learning loop | Persistence |
| BSA-13 | Export transactions as CSV/Excel | none (quick win, pull forward if time) |
| TD-007/008 | Split monolithic analyzer + shared column detection | none (do before parser grows further) |
| TD-023/024 | Magic-byte validation + dedup | none |
| TD-018 | TransactionTable virtualization | before history inflates row counts |
| BSA-08/11 | Anomaly detection / SSE streaming | parked (see brainstorm Tier 4) |

---

## Definition of Done

- **TD-033:** unit test proves an LLM category lands on the *correct* transaction; uploading a statement with unknown merchants now shows filled categories with `llm_enriched=True`.
- **TD-034:** `merchant_insights` includes LLM-filled merchants.
- **TD-035:** a statement with 200 uncategorized rows returns within a bounded time (config'd budget), not minutes.
- **TD-036/037:** summary rejects bad input with 422 not 500; no `localhost:5000` string anywhere in `frontend/`.
- **BSA-18:** `backend/` is gone; `pytest -m "not integration"` green in `backend-v2/`; CI workflow runs on push.
- **BSA-12:** dashboard shows a working summary card sourced from the live endpoint.
- **ADR-002:** committed at `docs/adr-002-persistence.md` with a data model and a decision.

---

## Upcoming Sprints — Rolling Roadmap

A directional view, not a commitment. Re-planned at each sprint kickoff.

### Sprint-04 — "Persistence + Longitudinal v1"
Build the SQLite store (BSA-19). Statement dedup (TD-024). First longitudinal feature: month-over-month comparison (BSA-17). This is the sprint where the product stops being a stateless parser and starts being a financial picture.

### Sprint-05 — "Intelligence on the History"
True recurring/subscription detection across months (BSA-07). Budgets & alerts. Category-correction learning loop (BSA-16) now that there's somewhere to store corrections.

### Sprint-06 — "Conversational + Hardening"
Natural-language Q&A over the history (BSA-06). Parser hardening: TD-007/008 split, magic-byte validation (TD-023), table virtualization (TD-018). Possibly the OCR spike for scanned PDFs if demand is real.

### Continuous (every sprint)
- One tech-debt item retired per sprint (don't let the register grow).
- Study doc + changelog updated (mandatory per `CLAUDE.md`).
- Tests added for every new feature per `docs/testing-strategy.md §7`.

---

## Architecture Decisions Needed This Sprint

| Decision | Recommendation |
|----------|----------------|
| Persistence engine | SQLite via SQLModel (single-user); Postgres migration path documented but not built |
| Category taxonomy | One canonical list shared by regex + LLM paths; pick the human-readable LLM set ("Food & Dining") and map regex output onto it |
| When to delete Flask | Now — suite is green, cutover held, rollback window served its purpose |

---

## Key Risks

| Risk | Mitigation |
|------|-----------|
| Persistence design rushed to "just ship it" | Keep it P2 *design-only* this sprint; resist coding it until the model is reviewed |
| Fixing TD-033 reveals the LLM output quality is poor | The fix is about *plumbing*; a separate eval is a later concern. Ship the correct plumbing, measure quality after |
| Deleting Flask removes a rollback before the fast-follows are verified | Sequence Block A (fixes verified green) **before** Block B (delete Flask) |
| Scope creep into Tier 3/4 features | The sprint goal is explicit: finish, don't start |

---

*Prompts: `docs/prompts/sprint-03/` · Brainstorm: `docs/feature-brainstorm.md` · Tech debt: `docs/tech-debt.md` · Previous: `docs/sprint-02-plan.md`*
