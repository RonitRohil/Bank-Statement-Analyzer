# Sprint-03 Prompt Files — Placeholder

Sprint-03 scope to be determined after Sprint-02 closes.

## Candidate Items (from Sprint-02 backlog)

| Ticket | Description | Complexity |
|--------|-------------|------------|
| BSA-06 | Natural language Q&A (`POST /api/chat`) | High — needs conversation state |
| BSA-07 | Recurring transaction detection | Medium — stats on transaction arrays |
| BSA-08 | Anomaly detection (IsolationForest) | High — needs training data |
| BSA-11 | SSE streaming progress bar during analysis | Medium — FastAPI EventSourceResponse |
| BSA-12 | Frontend filters, search, date range picker | Medium — frontend-only |
| BSA-13 | Export transactions as CSV | Low — frontend download |
| BSA-14 | Docker + docker-compose | Medium — after Flask decommission |
| BSA-15 | Smart spending insights (no LLM, stats-based) | Low — pure math |
| BSA-16 | Inline category correction (localStorage) | Medium — frontend + schema change |
| BSA-17 | Multi-statement comparison endpoint | High — needs history store design |
| TD-007 | Split monolithic analyzer into modules | High — architectural refactor |
| TD-001 | CI guard for requirements.txt encoding | Low — GitHub Actions step |

## Prerequisite Before Sprint-03 Planning

- BSA-09 (Flask cutover) must be shipped
- Decide whether to add a persistence layer (SQLite or Postgres) for history
- If persistence: design the data model before BSA-06, BSA-07, BSA-17

## Architecture Question for Sprint-03

**Do we need a database?**

Current: stateless — every request analyzes from scratch, no history  
Future features (chat, recurring detection, month comparison) all need history  

Options:
1. **SQLite** — zero infra, local file, good for single-user personal project
2. **PostgreSQL** — production-ready, needed if multi-user
3. **File-based** — store transaction history as JSON files keyed by statement hash

Recommend: SQLite via SQLModel (FastAPI's native ORM) for Sprint-03. Add migration path to Postgres if this becomes multi-user.

This decision should be made at Sprint-03 kickoff, not before.
