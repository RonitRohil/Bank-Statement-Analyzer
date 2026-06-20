# Sprint-04 Plan

**Sprint dates:** 2026-07-05 → 2026-07-19 (2 weeks)  
**Capacity:** Moderate — evenings + weekends (~12 hours)  
**Backend:** FastAPI (`backend/`) only — Flask is gone.

---

## Sprint Goal

**Turn the stateless parser into a stateful financial picture.**

Sprint-03 made everything work and visible for a single statement. Sprint-04's job is to make the data _persist_ so the product can stop being a one-shot tool and start being a financial record. The P0 is BSA-19 (SQLite/SQLModel store); everything else is either a dependency cleanup or a quick win that requires no persistence.

By end of sprint: a user uploads two statements from different months and the app knows about both; duplicate uploads return instantly; the transaction table shows an "AI" badge on LLM-enriched rows; export to CSV works; and three trivial schema gaps (TD-039/040/041) are closed in the first commit.

---

## Theme: "The database decision was made in Sprint-03. Build it."

See `docs/adr-002-persistence.md` for the full design. This sprint is implementation, not design. Don't relitigate SQLite vs. Postgres. Build the three-table schema, the Alembic migration, the dedup check, and the optional `persist=true` toggle. The stateless path must continue to work unchanged.

---

## P0 — Must Ship

### Housekeeping block (do first, ~30 min total)

These are one-liners that should be the first commit of the sprint.

| Ticket | Fix                                                                | Est.   |
| ------ | ------------------------------------------------------------------ | ------ |
| TD-039 | Add `insights: list[str] = []` to `AnalysisResult` in `schemas.py` | 5 min  |
| TD-040 | Add `currency: str = "INR"` to `SummaryResponse` in `schemas.py`   | 5 min  |
| TD-041 | `rmdir backend && git mv backend-v2 backend` — complete the rename | 5 min  |
| TD-038 | "AI" badge on enriched rows in `TransactionTable.tsx`              | 30 min |

### BSA-19 — Persistence implementation (SQLite / SQLModel)

**Design:** `docs/adr-002-persistence.md` — read it before writing a line.  
**Prompt:** `docs/prompts/sprint-04/01-persistence.md`  
**Est.:** 4–6h

Three tables: `statements`, `transactions`, `corrections`. Add `sqlmodel` + `alembic` to `requirements.txt`. Wire into the analyze endpoint behind an optional `persist=true` query param (or config toggle) — the stateless path must be unchanged. Hash check before parsing (dedup). `alembic init`, first migration.

**Definition of done:**

- `pytest` still green after the migration init
- Upload a statement twice → second call returns the cached result from DB (no re-parse)
- Upload two statements → both are stored; `GET /api/statements` returns them
- Stateless path (no `persist` flag) → behavior identical to today

**Open questions BSA-19 must answer** (per ADR-002):

- Encryption at rest: SQLCipher, OS-level full-disk, or none + documented disclaimer?
- Data retention policy: delete statements older than N months, or never?
- Alembic init location: `backend/alembic/` alongside `app/`

**Constraints:**

- SQLModel only (not raw SQLAlchemy)
- In-memory SQLite for tests (`sqlite:///:memory:`)
- Pydantic models (`Transaction`, `AccountInfo`) must not be modified to be SQLModel table models — keep them separate; write dedicated `StatementDB`, `TransactionDB` table models in `app/db/models.py`

### TD-024 — Transaction deduplication

**Files:** `backend/app/models/analyzer.py`  
**Prompt:** `docs/prompts/sprint-04/02-dedup.md`  
**Est.:** 1–2h

Dedupe on `(date, amount, narration, balance)` before confidence scoring. Multi-page PDF stitching (TD-021) increased overlap risk — two adjacent pages may extract the same boundary row twice. Priority rises this sprint because persistence will start storing transactions; duplicates in the DB are worse than duplicates in a transient response.

---

## P1 — Ship if Capacity Allows

### BSA-13 — Export transactions to CSV / Excel

**Prompt:** `docs/prompts/sprint-04/03-export.md`  
**Est.:** 2–3h

The #1 reason people parse a bank PDF is to get the data _out_ of the PDF. This closes the loop. Options:

- **CSV (backend):** New endpoint `GET /api/analyze/bank/export?format=csv` that accepts the same transactions body and streams a CSV response. Reuse `pandas.DataFrame.to_csv()`.
- **Excel (backend):** Same endpoint with `?format=xlsx`, using `openpyxl` (already in requirements).
- **Frontend:** A "Download CSV" and "Download XLSX" button below the TransactionTable. `Blob` + `URL.createObjectURL`.

Start with CSV only; Excel is a stretch.

### BSA-07 (lite) — Single-statement recurring detection

**Prompt:** `docs/prompts/sprint-04/04-recurring-detection.md`  
**Est.:** 2–3h

Identify likely recurring charges within a single statement. A merchant appearing ≥3 times with a coefficient of variation < 0.25 on amounts qualifies. Return a `recurring_candidates` array in the analyze response. Render in the frontend as a "Likely Subscriptions" section, or as enhanced insight callouts (teaser already in the Insights Strip from BSA-15).

Note: The Insights Strip already shows one recurring teaser (BSA-15 Sprint-03). This ticket formalizes it into a structured list in the API response and a dedicated UI section.

---

## P2 — Backlog (Sprint-05+)

| Ticket        | Description                              | Gated on                             |
| ------------- | ---------------------------------------- | ------------------------------------ |
| BSA-17        | Month-over-month comparison              | Persistence (BSA-19)                 |
| BSA-07 (full) | True cross-statement recurring detection | Persistence                          |
| BSA-06        | Natural-language Q&A                     | Persistence                          |
| BSA-16        | Category-correction learning loop        | `corrections` table (BSA-19)         |
| TD-007/008    | Analyzer split + shared column detection | none (defer to Sprint-05)            |
| TD-018        | TransactionTable virtualization          | Before history inflates row counts   |
| TD-023        | Magic-byte upload validation             | none                                 |
| TD-019        | Docker + compose                         | none (unblocked since Flask deleted) |

---

## Architecture Decisions Needed This Sprint

| Decision                    | Recommendation                                                                                                                                                                                                         |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Encryption at rest          | None for now + documented disclaimer is acceptable for a personal tool. SQLCipher adds a dependency and ops burden. Revisit if deployed or shared.                                                                     |
| Data retention              | No automatic deletion. Document that the `.db` file is the user's responsibility to back up and prune.                                                                                                                 |
| `GET /api/statements` shape | Return `[{id, file_hash, original_filename, bank_name, account_number, period_from, period_to, uploaded_at, confidence_overall}]`. No transaction payload — that's a separate `GET /api/statements/{id}/transactions`. |
| Export endpoint method      | `POST` (body contains transactions) rather than `GET` — avoid URL length limits on large transaction arrays.                                                                                                           |

---

## Capacity Planning

| Work                                    | Est.       | Priority |
| --------------------------------------- | ---------- | -------- |
| Housekeeping block (TD-039/040/041/038) | 1h         | P0       |
| BSA-19 persistence implementation       | 4–6h       | P0       |
| TD-024 transaction dedup                | 1–2h       | P0       |
| BSA-13 CSV export                       | 2–3h       | P1       |
| BSA-07 lite recurring detection         | 2–3h       | P1       |
| **P0 total**                            | **6–9h**   |          |
| **Total (all P0+P1)**                   | **10–15h** |          |

**Plan P0 only** (~7h). BSA-13 is the first pull-forward if sprint completes ahead of schedule — no prerequisites, high user value.

---

## Definition of Done

- **TD-039/040:** `schemas.py` updated; Swagger UI shows the new fields.
- **TD-041:** `backend/` is the directory name; CI references `backend/`, not `backend-v2/`.
- **TD-038:** Rows with `llm_enriched: true` show an "AI" indicator in the category cell.
- **BSA-19:** Duplicate upload returns stored result in < 100ms; new upload stores all transactions; `pytest` green including new DB fixtures; encryption decision documented.
- **TD-024:** Uploading a test statement with known duplicate rows (same date/amount/narration) returns deduped count.
- **BSA-13 (if shipped):** `POST /api/analyze/bank/export?format=csv` returns a valid CSV; "Download CSV" button appears in the dashboard.

---

## Key Risks

| Risk                                               | Mitigation                                                                                                                                                                                     |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Alembic + SQLModel setup consumes the whole sprint | The design is done (ADR-002) — implementation should be mechanical. Timebox the migration setup to 1h; if blocked, use raw SQLite via `sqlite3` stdlib as a fallback (swap to SQLModel later). |
| Persistence breaks the stateless path              | Stateless path gated behind a flag or config from day 1. Add a test that hits `/api/analyze/bank/statement` _without_ `persist=true` and asserts no DB writes occurred.                        |
| Dedup hash collisions                              | SHA-256 of the file bytes is the dedup key. Collision probability is negligible for a personal tool.                                                                                           |
| Export endpoint body too large                     | Bank statements rarely exceed 1,000 transactions (< 500KB JSON). Not a real risk at this scale.                                                                                                |

---

## Claude Code Prompts

To be generated in `docs/prompts/sprint-04/`:

| File                 | Purpose                                                       |
| -------------------- | ------------------------------------------------------------- |
| `00-overview.md`     | Sprint context + sequencing for Claude Code                   |
| `01-housekeeping.md` | TD-039/040/041/038 — schema fields + AI badge                 |
| `02-persistence.md`  | BSA-19 — full SQLModel + Alembic + dedup implementation       |
| `03-dedup.md`        | TD-024 — transaction dedup in analyzer.py                     |
| `04-export.md`       | BSA-13 — CSV/Excel export endpoint + frontend button          |
| `05-recurring.md`    | BSA-07 lite — recurring detection + structured response field |

---

## Upcoming Sprints — Rolling Roadmap

### Sprint-05 — "Longitudinal Intelligence v1"

Month-over-month comparison (BSA-17) — requires Sprint-04 persistence. True cross-statement recurring detection (BSA-07 full). TD-007/008 analyzer split (set up for parser extensibility before adding more parsers).

### Sprint-06 — "Conversational + Hardening"

Natural-language Q&A over stored history (BSA-06). Category-correction learning loop (BSA-16 — uses `corrections` table from BSA-19). Parser hardening: magic-byte validation (TD-023), table virtualization (TD-018), OCR spike if demand is real.

### Continuous (every sprint)

- One architecture tech-debt item retired per sprint.
- Study doc + changelog updated at close (mandatory per `CLAUDE.md`).
- Tests for every new feature (per `docs/testing-strategy.md §7`).

---

_Design: `docs/adr-002-persistence.md` · Tech debt: `docs/tech-debt.md` · Brainstorm: `docs/feature-brainstorm.md` · Previous: `docs/sprint-03-plan.md`_
