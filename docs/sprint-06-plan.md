# Sprint-06 Plan

**Sprint dates:** 2026-07-06 → 2026-07-20 (2 weeks)
**Capacity:** Moderate — evenings + weekends (~12 hours)
**Backend:** FastAPI (`backend/`). Frontend: React + TypeScript (`frontend/`).

---

## Sprint Goal

**Turn the longitudinal data into a conversational and self-correcting product.**

Sprint-05 proved the stored data is useful — month-over-month charts and confirmed recurring subscriptions are real, compelling features. Sprint-06 goes one step further: let the user _ask questions_ about their history in plain language (BSA-06), see and manage all their uploaded statements (BSA-20), and start teaching the system when it gets categories wrong (BSA-16 learning loop). The housekeeping block closes 3 quick CR-S5 findings before any new features land.

By end of sprint: a user can type "how much did I spend on food in February?" and get a real answer from their stored transaction history. They can also browse their statement archive, delete old uploads, and correct a miscategorized transaction so future imports get it right.

---

## Theme: "Conversational + Correctable"

The product has been stateless → stateful → longitudinal. The next leap is making it _conversational_ — not just showing data but responding to questions about it. BSA-06 is the headline. BSA-16 closes the feedback loop: users can fix what the parser got wrong, and those corrections influence future parses. BSA-20 makes the archive visible and manageable.

---

## P0 — Must Ship

### Housekeeping block (first commit, ~30 min)

From Sprint-05 code review — three trivial fixes, zero risk:

| Ticket   | Fix                                                                       | Est.   |
| -------- | ------------------------------------------------------------------------- | ------ |
| CR-S5-05 | Add `.limit(5000)` cap in `get_monthly_summary()` inner transaction query | 15 min |
| CR-S5-01 | Add route ordering comment above `/{statement_id}` in `statements.py`     | 2 min  |
| CR-S5-04 | Add staleness comment on `recurring_candidates_json` in `crud.py`         | 2 min  |

These are the first commit of the sprint. No new features until these land.

### BSA-06 — Natural-language Q&A over transaction history

**Prompt:** `docs/prompts/sprint-06/02-nl-qa.md`
**Est.:** 4–6h
**Gated on:** BSA-19 (persistence ✅), `GET /api/statements/{id}/transactions` (✅ Sprint-05)

**What it does:** User types a question like "how much did I spend on Swiggy last month?" and gets a direct answer derived from their stored transaction history.

**Approach — tool-calling over SQLite (not RAG):**
RAG (embedding + similarity search) is overkill for structured financial data. The better approach is function-calling: give the LLM a set of typed query tools and let it pick the right one.

```
Tools exposed to the LLM:
  query_transactions(account_number?, start_date?, end_date?, category?, merchant?, txn_type?) → list
  get_monthly_summary(account_number, month) → MonthSummary
  list_statements(account_number?) → list[StatementDB metadata]
```

The LLM (Ollama `qwen2.5:7b` or Claude Haiku if configured) receives the question + tool definitions, picks a tool, we execute it against SQLite, return the result, and the LLM produces a plain-language answer.

**Backend:**

- New `backend/app/services/qa_engine.py` — `answer_question(question: str, account_number: str | None, session) → str`
- Defines 3 tool schemas as dicts (Ollama tool-calling format)
- Calls Ollama `/v1/chat/completions` with `tools=` parameter
- Executes the selected tool against the DB
- Returns the LLM's final answer (second pass with tool result in context)
- New `backend/app/routers/qa.py` — `POST /api/qa/ask`
  - Body: `{"question": "...", "account_number": "..." (optional)}`
  - Response: `{"answer": "...", "tool_used": "...", "data_points": N}`
- Register in `main.py`

**Frontend:**

- New `frontend/components/QAChat.tsx`
  - Simple input box + submit button + answer display area
  - Loading skeleton while waiting for LLM response
  - Shows `data_points` sub-text: "Based on 47 transactions"
  - Renders below `SubscriptionsCard` in `App.tsx`
  - Only visible when `persistedStatements.length > 0`

**Definition of done:**

- Upload 2+ statements, type "total spending in [month]" → correct answer
- Tool-calling falls back gracefully when Ollama is down (returns "QA unavailable — start Ollama")
- `pytest` green with ≥4 new tests for `qa_engine.py` (mocked Ollama responses)

---

### BSA-20 — Statement history UI

**Prompt:** `docs/prompts/sprint-06/03-history-ui.md`
**Est.:** 3–4h
**Gated on:** BSA-19 (✅), `GET /api/statements` (✅), `GET /api/statements/{id}/transactions` (✅ Sprint-05)

**What it does:** Adds a "History" tab/section where users can see all previously uploaded statements, reload a statement's transactions into the dashboard view, and delete old entries.

**Backend:**

- New `DELETE /api/statements/{id}` endpoint in `statements.py`
  - Deletes `TransactionDB` rows for the statement first (FK constraint), then `StatementDB` row
  - Returns 204 on success, 404 on unknown ID
- `GET /api/statements` already exists with pagination — no backend changes needed

**Frontend:**

- New `frontend/components/HistoryPanel.tsx`
  - Lists all stored statements (from `GET /api/statements`) with: bank name, account holder, period from/to, upload date, transaction count, confidence score
  - Two actions per row: "Load" (fetch transactions and reload the dashboard), "Delete" (confirm + call DELETE, remove from list)
  - "Load" calls `GET /api/statements/{id}/transactions` and merges result into `App.tsx` state — the charts and tables update to reflect that statement
  - Pagination: shows 20 at a time, "Load more" button
- `frontend/services/api.ts` — add `deleteStatement(id)` and `getStatementTransactions(id)` functions

**Definition of done:**

- Upload 3 statements → History panel shows all 3 → Load any one → dashboard shows its data → Delete one → it disappears from the list
- DELETE endpoint returns 204 on success, 404 on unknown ID

---

## P1 — Ship if Capacity Allows

### BSA-16 — Category-correction learning loop

**Prompt:** `docs/prompts/sprint-06/04-corrections.md`
**Est.:** 3–4h
**Gated on:** BSA-19 (✅ — `corrections` table already in schema)

The `CorrectionDB` table was designed in ADR-002 and created in the initial Alembic migration. It's been sitting unused since Sprint-04. This ticket wires it up.

**Backend:**

- `POST /api/corrections` — accepts `{fingerprint, corrected_category, corrected_merchant?}`
  - Fingerprint = `SHA-256 of f"{transaction_date}:{amount}:{narration[:100]}"` (already documented in `crud.py` comment from CR-S4-03)
  - Upserts into `CorrectionDB` (unique on fingerprint)
- `get_correction(fingerprint, session)` in `crud.py` — looks up a correction by fingerprint
- Modify `routers/analyze.py` — after enrichment, for each transaction, compute its fingerprint and check `CorrectionDB`. If found, override the transaction's category and merchant with the stored correction.

**Frontend:**

- Add "✏ Fix category" button per row in `TransactionTable.tsx`
- Opens an inline dropdown: pick from `CANONICAL_CATEGORIES` (16 options from `categories.py`)
- On select, computes fingerprint client-side (SHA-256 via Web Crypto API) and calls `POST /api/corrections`
- Visual feedback: row shows the corrected category with a "📌 Corrected" badge

**Definition of done:**

- Upload a statement, correct a transaction's category → correction stored in DB → re-upload same statement → corrected transaction shows the override category
- `pytest` green with ≥3 new tests (save correction, retrieve correction, override on re-parse)

---

### TD-018 — TransactionTable virtualization

**Prompt:** `docs/prompts/sprint-06/05-virtualization.md`
**Est.:** 2–3h
**Gated on:** None

Statements with 1,000+ transactions cause visible jank. With BSA-20 (history reload) increasing the chance that large statements are loaded, this becomes more likely to be user-visible.

**Approach:** Add `@tanstack/react-virtual` (already a common dep in the ecosystem). Virtualize `TransactionTable.tsx` to render only the visible rows (window of ~20–30) plus a buffer. Alternatively, implement simple client-side pagination (50 rows per page, prev/next buttons) — lower risk, no new dependency.

**Recommendation:** Client-side pagination is the safer Sprint-06 choice. `@tanstack/react-virtual` is a bigger dependency change and has edge cases with variable row heights (the category pills can make rows taller). Ship pagination now, virtualize in Sprint-07 if needed.

---

### TD-023 — Magic-byte upload validation

**Prompt:** `docs/prompts/sprint-06/06-magic-bytes.md`
**Est.:** 1–2h
**Gated on:** None

After extension whitelist check, read the first 8 bytes and verify against known signatures:

- PDF: `%PDF` (`25 50 44 46`)
- ZIP (XLSX/XLSB): `PK\x03\x04` (`50 4B 03 04`)
- CSV: no magic bytes — accept any text if extension is `.csv`

Add a helper `validate_magic_bytes(file_path, extension) -> bool` in `routers/analyze.py`. Return 400 if it fails. Add 2 tests.

---

## P2 — Backlog (Sprint-07+)

| Ticket   | Description                                       | Gated on                              |
| -------- | ------------------------------------------------- | ------------------------------------- |
| BSA-21   | Budget/alert thresholds per category              | BSA-20 history + category persistence |
| CR-S5-03 | Extract `parsers/utils.py` for shared utilities   | None (minor refactor)                 |
| CR-S5-02 | Surface `top_category` in `MonthlyComparison.tsx` | None                                  |
| CR-S5-06 | Fix MoM YAxis formatter                           | None                                  |
| CR-S5-07 | SubscriptionsCard monthly total caveat            | None                                  |
| TD-019   | Docker + docker-compose                           | Arch settling ✅                      |
| TD-025   | `transaction_reference` regex too greedy          | None                                  |
| TD-026   | Confidence penalizes balance-less formats         | None                                  |

---

## Architecture Decisions Needed This Sprint

| Decision                                  | Recommendation                                                                                                                                                                                          |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q&A: tool-calling vs RAG                  | Tool-calling over SQLite — structured financial data doesn't need embedding. RAG is overhead when the schema is known.                                                                                  |
| Q&A: Ollama vs Claude API                 | Ollama `qwen2.5:7b` for local dev (free, already in use). Claude Haiku configurable via env var for production. Use the same pattern as `llm_enricher.py`.                                              |
| Correction fingerprint: client or server? | Server is safer — guarantees the hash algorithm matches `crud.py`. But requires an extra round-trip if the UI wants to show "corrected" state before submitting. Accept the round-trip for correctness. |
| History UI: tab or inline section?        | Inline section (below SubscriptionsCard) for now. A full tab requires a router (`react-router-dom`) which is a bigger dependency change. Defer tab-based navigation to Sprint-07.                       |
| DELETE statement: cascade or manual?      | Manual: delete `TransactionDB` rows first (WHERE statement_id = N), then the `StatementDB` row. Don't rely on SQLite foreign key cascade since SQLite FK enforcement is off by default.                 |

---

## Capacity Planning

| Work                                   | Est.        | Priority |
| -------------------------------------- | ----------- | -------- |
| Housekeeping (CR-S5-01/04/05)          | 30 min      | P0       |
| BSA-06 Q&A backend                     | 3–4h        | P0       |
| BSA-06 Q&A frontend                    | 1–2h        | P0       |
| BSA-20 history UI (backend + frontend) | 3–4h        | P0       |
| BSA-16 category corrections            | 3–4h        | P1       |
| TD-018 table pagination                | 2–3h        | P1       |
| TD-023 magic-byte validation           | 1–2h        | P1       |
| **P0 total**                           | **~8–10h**  |          |
| **Total (all P0+P1)**                  | **~13–17h** |          |

**Plan P0 only (~10h).** BSA-16 is the first pull-forward. TD-018 and TD-023 are second.

---

## Definition of Done

- **CR housekeeping:** All three fixes committed together as first commit. `pytest` green.
- **BSA-06:** `POST /api/qa/ask` responds with a plain-language answer; falls back gracefully when Ollama is down; ≥4 tests pass.
- **BSA-20:** `DELETE /api/statements/{id}` returns 204 (success) / 404 (unknown); `HistoryPanel.tsx` shows all statements; Load and Delete actions work end-to-end.
- **BSA-16 (if shipped):** `POST /api/corrections` stores a correction; re-parsing the same file applies the override; ≥3 tests pass.
- **Full test suite green** after every item.

---

## Key Risks

| Risk                                        | Mitigation                                                                                                                                                                                              |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ollama tool-calling support varies by model | `qwen2.5:7b` supports Ollama's tool-calling spec. Test with `ollama run qwen2.5:7b` before building the integration. Fall back to prompt-based tool selection if needed (parse JSON from model output). |
| Q&A latency is high                         | Two LLM round-trips (tool selection + answer generation). Cap each at 30s via `asyncio.wait_for`. Return partial/fallback if timed out.                                                                 |
| DELETE with FK constraints                  | SQLite FK enforcement is off by default. Always delete `TransactionDB` rows before `StatementDB` row in the DELETE endpoint. Add an integration test that confirms the transactions are gone.           |
| BSA-16 fingerprint drift                    | If `narration[:100]` changes (whitespace normalization, encoding), the fingerprint won't match. Normalize narration before fingerprinting (strip + lowercase). Document the normalization in a comment. |

---

## Claude Code Prompts

In `docs/prompts/sprint-06/`:

| File                   | Purpose                                                                  |
| ---------------------- | ------------------------------------------------------------------------ |
| `00-overview.md`       | Sprint context + sequencing for Claude Code                              |
| `01-housekeeping.md`   | CR-S5-01/04/05 — route comment, staleness comment, query limit           |
| `02-nl-qa.md`          | BSA-06 — NL Q&A service + endpoint + frontend chat widget                |
| `03-history-ui.md`     | BSA-20 — DELETE endpoint + HistoryPanel.tsx                              |
| `04-corrections.md`    | BSA-16 — POST /api/corrections + re-parse override + frontend fix button |
| `05-virtualization.md` | TD-018 — Client-side pagination for TransactionTable                     |
| `06-magic-bytes.md`    | TD-023 — Magic-byte validation in upload handler                         |

---

## Upcoming Sprints — Rolling Roadmap

### Sprint-07 — "Production Readiness"

Docker + docker-compose (TD-019). Budget/alert thresholds (BSA-21). `transaction_reference` regex fix (TD-025). Confidence scorer improvements (TD-026). `@tanstack/react-virtual` proper virtualization if pagination isn't enough (TD-018-full). OCR spike for scanned PDFs if demand is real.

### Sprint-08 — "Polish + Scale"

Multi-account dashboard view. Statement comparison UI (pick any two statements, diff them). Export improvements (PDF report of the analysis). Performance profiling + SQLite index review. Mobile-responsive layout pass.

### Continuous (every sprint)

- One architecture tech-debt item retired per sprint.
- Study doc + changelog updated at close (mandatory per `CLAUDE.md`).
- Tests for every new feature; keep `pytest` green.

---

_Architecture: `docs/architecture.md` · Tech debt: `docs/tech-debt.md` · Previous sprint: `docs/sprint-05-plan.md` · Feature brainstorm: `docs/feature-brainstorm.md`_
