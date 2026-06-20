# Sprint-03 Prompt Files — Overview

**Sprint:** 2026-06-20 → 2026-07-04
**Plan:** `docs/sprint-03-plan.md`
**Theme:** Finish Sprint-02's two half-built features, decommission Flask, design persistence. Don't start new things while old things are half-built.

These prompts are written for Claude Code (CLI). Each follows the project prompt format (Context → Files to read first → Change → Constraints → Verification → Commit message). Work them **in order** — Block A fixes must be verified green *before* Block B deletes Flask (it's the rollback).

---

## Execution Order

| # | Prompt | Ticket(s) | Priority | Est. | Depends on |
|---|--------|-----------|----------|------|-----------|
| 01 | `01-llm-enricher-fix.md` | TD-033, TD-034 | P0 | 2–3h | — |
| 02 | `02-frontend-url-cleanup.md` | TD-037 | P0 | 20m | — |
| 03 | `03-summary-typing.md` | TD-036 | P0 | 30m | — |
| 04 | `04-bound-enrichment.md` | TD-035, CR-S2-08 | P0 | 2h | 01 |
| 05 | `05-delete-flask.md` | BSA-18 | P0 | 1–2h | 01–04 green |
| 06 | `06-summary-frontend.md` | BSA-12, TD-038 | P1 | 3–4h | 03 |
| 07 | `07-smart-insights.md` | BSA-15 | P1 | 3–4h | — |
| 08 | `08-adr-persistence.md` | ADR-002 | P2 (design) | 2h | — |

## Definition of Done (sprint)

See `docs/sprint-03-plan.md` → "Definition of Done". Every code prompt ends with: tests added (`docs/testing-strategy.md §7`), study/changelog updated (`CLAUDE.md` rules).
