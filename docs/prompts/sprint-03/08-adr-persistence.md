# Prompt: Persistence Layer Decision (ADR only) — ADR-002

**Task:** Write an Architecture Decision Record for adding a persistence layer, and design the data model. **This prompt produces a document, not code.**
**Sprint ref:** Sprint-03 · Ticket: ADR-002
**Refs:** `docs/feature-brainstorm.md` Tier 3, `docs/improvement-analysis.md`, `docs/prompts/sprint-03/00-overview.md`
**Estimated time:** 2 hours

---

## Why This Change Is Needed

Almost every high-value future feature — month-over-month comparison (BSA-17), true recurring detection (BSA-07), natural-language Q&A (BSA-06), category-correction learning (BSA-16) — needs to store data across uploads. The project keeps deferring this decision, which silently blocks the entire longitudinal roadmap. Sprint-03 makes the decision and designs the model so Sprint-04 can implement without re-litigating it.

This is a **design** task. Do not add a database, an ORM dependency, or migrations this sprint. Produce a reviewed ADR and data model.

## Files to Read First

1. `docs/adr-001-flask-vs-fastapi.md` — match this ADR format
2. `docs/feature-brainstorm.md` — Tier 3 (which features need persistence) and the SQLite recommendation
3. `docs/architecture.md` — current stateless data flow
4. `backend-v2/app/models/schemas.py` — the `Transaction`/`AccountInfo` shapes the schema must persist

## Deliverable: `docs/adr-002-persistence.md`

Follow ADR-001's structure. Cover:

### Context
- Current state: stateless, every upload re-analyzed, nothing stored.
- The features blocked by the absence of storage (list them with ticket refs).
- Constraints: single-user personal project today; evenings/weekends maintenance; possible multi-user "someday" but no concrete requirement.

### Options (with honest trade-offs)
1. **SQLite via SQLModel** — zero infra, one file, native to FastAPI's author; weak concurrency, single-writer.
2. **PostgreSQL** — production-grade, real concurrency; needs a running server / container, heavier for a personal app.
3. **File-based JSON keyed by statement hash** — dead simple, no dependency; no querying, no relations, doesn't scale to "compare across months" cleanly.

### Decision
Recommend **SQLite via SQLModel** with a documented migration path to Postgres if multi-user ever becomes real. State *why* (lowest infra cost for the only user who exists; SQLModel reuses the Pydantic models already in the codebase).

### Data Model (the design)
Propose tables and key columns:
- `statements` — id, file_hash (for dedup, ties to TD-024), account_number, bank_name, period_from, period_to, uploaded_at, confidence_overall.
- `transactions` — id, statement_id (FK), date, amount, type, narration, balance, merchant, category, payment_method, confidence_score, llm_enriched.
- `corrections` — id, transaction fingerprint (date+amount+narration hash), corrected_category, corrected_merchant, created_at. (Feeds BSA-16.)

Include a note on **statement deduplication** (file_hash) and **PII at rest** (this stores real financial data on disk — note encryption-at-rest / retention as an open question for the implementation prompt).

### Consequences
- Unlocks BSA-06/07/16/17.
- Adds a migration story, a backup story, and a data-retention/privacy obligation.
- `analyze` becomes optionally stateful (persist on upload) — design it so the stateless path still works (storage is additive, not required).

## Constraints

- **No code.** Document only. The implementation is BSA-19 (Sprint-04), which will get its own prompt.
- Be decisive — the ADR must end with a clear recommendation, not a menu.
- Keep the data model small; resist modeling features that aren't committed yet.

## Verification Steps

1. `docs/adr-002-persistence.md` exists, follows ADR-001's format, ends with a clear decision.
2. The data model covers dedup (TD-024) and the correction-learning loop (BSA-16).
3. Linked from `docs/architecture.md` and `docs/sprint-03-plan.md`.

## After This Task

Log the decision in `docs/changelog.md` (Type: Architecture decision). Add BSA-19 (implement persistence) to the Sprint-04 section of `docs/sprint-03-plan.md` roadmap. No study doc needed (the ADR *is* the artifact).
