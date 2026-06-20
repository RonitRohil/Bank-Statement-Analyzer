# Sprint-04 Prompt Overview

**Sprint:** Sprint-04 (2026-07-05 → 2026-07-19)  
**Goal:** Turn the stateless parser into a stateful financial picture.  
**Context:** Sprint-03 made everything visible for a single statement. Sprint-04 adds persistence, dedup, export, and a recurring-detection foundation.

## Sequencing

Run prompts **in numbered order**. Each one's changes are a prerequisite for the next.

| Prompt               | Ticket             | What it does                         | ~Time  |
| -------------------- | ------------------ | ------------------------------------ | ------ |
| `01-housekeeping.md` | TD-039/040/041/038 | Schema fixes + AI badge + rename     | 30 min |
| `02-persistence.md`  | BSA-19             | SQLModel + Alembic + dedup check     | 4–6h   |
| `03-dedup.md`        | TD-024             | Transaction dedup in analyzer.py     | 1–2h   |
| `04-export.md`       | BSA-13             | CSV/Excel export endpoint + button   | 2–3h   |
| `05-recurring.md`    | BSA-07 lite        | Single-statement recurring detection | 2–3h   |

## What You Must Read Before Starting

- `docs/adr-002-persistence.md` — full data model design; do not deviate without logging a decision
- `docs/sprint-04-plan.md` — constraints and definition of done for each ticket
- `docs/tech-debt.md` — current open items (TD-039, 040, 041, 038, 024)
- `CLAUDE.md` — workflow rules (read before write, small patches, explain each change)

## Definition of Done for the Sprint

- `pytest` green throughout (add tests for every new service/endpoint)
- No `backend-v2/` references remain in any live file
- `docs/changelog.md` updated with an entry for every prompt completed
- `docs/tech-debt.md` updated: close items you fix, open any new ones you discover
- `docs/study/sprint-04-learnings.md` written at close
