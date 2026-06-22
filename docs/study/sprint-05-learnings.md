# Sprint-05 Learnings — "Make the Stored Data Earn Its Keep"

**Sprint dates:** 2026-06-22 (condensed single session)
**Status:** Complete — all P0 and P1 shipped
**Theme:** Longitudinal intelligence on top of Sprint-04's persistence foundation

---

## What Was Built

Sprint-05 delivered everything on the P0 and P1 list. The housekeeping block landed first, then BSA-17, then BSA-07-full, then the analyzer split. All four shipped in one sprint.

| Ticket            | What shipped                                                                    | Key files                                                                                                                                   |
| ----------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| CR-S4-01/02/03/05 | Housekeeping — pagination, transactions endpoint, export sanitize, crud comment | `routers/statements.py`, `routers/export.py`, `db/crud.py`                                                                                  |
| BSA-17            | Month-over-month comparison endpoint + frontend chart                           | `db/crud.py`, `routers/statements.py`, `schemas.py`, `MonthlyComparison.tsx`                                                                |
| BSA-07-full       | Cross-statement recurring detection endpoint + Alembic migration                | `db/crud.py`, `routers/statements.py`, `schemas.py`, `SubscriptionsCard.tsx`, `alembic/versions/a1b2c3d4e5f6_*`                             |
| TD-007/008        | Split monolithic `BankStatementAnalyzer` into focused modules                   | `parsers/excel_parser.py`, `parsers/pdf_parser.py`, `enrichers/narration_enricher.py`, `scorers/confidence_scorer.py`, `models/analyzer.py` |

Test count: ~38 (Sprint-04 end) → ~46 (Sprint-05 close, +4 comparison + 4 recurring).

---

## Why It Was Built

Sprint-04 proved the database decision correct — data persists, dedup works, history accumulates. Sprint-05's job was to make that stored data _visible and useful_. A pile of SQLite rows is not a product; a month-over-month chart is.

The four Sprint-05 items map to four different categories of value:

- **CR housekeeping** — close the gap between a code review finding and a shipped fix; small but forces discipline.
- **BSA-17 (MoM)** — the single most-requested longitudinal feature. "Did I spend more this month than last?" is the core question every personal finance tool answers.
- **BSA-07-full (recurring)** — cross-statement detection closes the loop on BSA-07 lite from Sprint-04. Showing a `↻` pill on a single statement is a teaser; surfacing "NETFLIX, 3 statements, ₹649/mo" is a real finding.
- **TD-007/008 (split)** — structural. The monolithic analyzer was a 1,280-line class where parsers, enrichers, and scorers were tangled. Every future parser extension (OCR, new bank format) required editing the same file. This sprint paid that debt before it compounded.

---

## How It Works

### 1. Housekeeping Block (CR-S4-01/02/03/05)

Four CR findings from the Sprint-04 review, bundled into the first commit:

**CR-S4-01 — Pagination on `GET /api/statements`:**
`routers/statements.py` `list_statements()` now accepts `limit` (default 20, max 100) and `offset` as query params. Uses SQLModel's `.offset()` and `.limit()` — no manual slicing. The response envelope mirrors the request params: `{"statements": [...], "limit": 20, "offset": 0}`.

**CR-S4-02 — `GET /api/statements/{id}/transactions`:**
New endpoint in `statements.py`. Queries `TransactionDB` filtered by `statement_id`, with its own `limit`/`offset` pagination (default 100, max 500). Returns 404 if no transactions found for that ID (statement unknown or zero transactions). This endpoint was the blocker for the history UI and the compare endpoint.

**CR-S4-03 — CorrectionDB fingerprint comment:**
One-line comment added to `crud.py` documenting the fingerprint format: `SHA-256 of f"{transaction_date}:{amount}:{narration[:100]}"`. This matters because BSA-16 (category-correction learning) will need to write corrections using the same key — without a comment, there was a real risk of drift when BSA-16 is implemented later.

**CR-S4-05 — Export filename sanitization:**
`routers/export.py` now runs the `filename` query param through `re.sub(r"[^\w\-.]", "_", req.filename)` before building the `Content-Disposition` header. Prevents path traversal via crafted filenames. The sanitized name replaces any non-word, non-dash, non-dot character with `_`.

---

### 2. BSA-17 — Month-over-Month Comparison

**Backend — `get_monthly_summary()` in `crud.py`:**

The algorithm:

1. Query all `StatementDB` rows matching the given `account_number`, ordered by `period_from ASC`.
2. For each statement, load all its `TransactionDB` rows.
3. Slice `transaction_date[:7]` to get `"YYYY-MM"` keys and bucket transactions.
4. Per-bucket: accumulate `income` (CREDIT txns) and `expenses` (DEBIT txns), track category totals.
5. After all statements processed, sort buckets by month, compute `delta_expenses_pct` = `((current - previous) / previous) * 100` (null for the first month, null if previous expenses = 0).
6. Return the sorted list as `list[dict]` — schemas handle validation upstream.

**Schemas added:**

```python
class MonthSummary(BaseModel):
    month: str          # "YYYY-MM"
    income: float
    expenses: float
    net: float
    transaction_count: int
    top_category: str | None
    delta_expenses_pct: float | None

class ComparisonResponse(BaseModel):
    account_number: str
    months: list[MonthSummary]
    total_months: int
```

**Endpoint:**
`GET /api/statements/compare?account_number=XXXX` → 200 with `ComparisonResponse`, 404 if no statements for that account.

**Route ordering matters:** FastAPI matches routes top-to-bottom. `GET /api/statements/compare` must appear _before_ `GET /api/statements/{statement_id}/transactions` in `statements.py`, otherwise FastAPI would try to interpret `"compare"` as a statement ID integer and 422. This was an explicit ordering decision in the implementation.

**Frontend — `MonthlyComparison.tsx`:**

- Recharts `ComposedChart`: two `Bar` (income/expense) + one `Line` (net).
- Single-month graceful render: shows the chart with one data point + an amber warning "Upload more statements to see trends."
- Summary tile row below the chart shows expenses for the last 4 months at a glance.
- Rendered in `App.tsx` below the main dashboard. The component appears whenever `persistedMonths.length > 0` — not gated on ≥2 months, because a single data point is still valid context.
- `compareStatements()` in `api.ts` calls the endpoint on statement persist. Separate `getConfirmedRecurring()` call follows to populate `SubscriptionsCard`.

**Tests — `test_comparison.py` (4 tests):**

- `test_compare_single_month` — one statement, delta is null.
- `test_compare_two_months` — two statements, Feb debit double Jan → `delta_expenses_pct == 100.0`.
- `test_compare_404_unknown_account` — unknown account → 404.
- `test_compare_no_account_param` — missing required param → 422.

The test fixture uses `StaticPool` (single shared connection) so that `save_statement()` writes in the fixture session are visible to the HTTP client's dependency-overridden session. Without `StaticPool`, in-memory SQLite creates a new database per connection and the test would always get empty results.

---

### 3. BSA-07-full — Cross-Statement Recurring Detection

**Alembic migration** (`a1b2c3d4e5f6_add_recurring_candidates_json_to_statements.py`):
Adds `recurring_candidates_json: Optional[str]` to `StatementDB`. Stores the `recurring_candidates` list from BSA-07 lite as JSON. Existing rows default to `NULL` (treated as `[]` in queries).

**`save_statement()` updated:**
Now accepts an optional `recurring_candidates: list | None = None` argument. Serializes to `json.dumps(recurring_candidates or [])` before storing in `recurring_candidates_json`.

**`get_cross_statement_recurring()` in `crud.py`:**
Algorithm:

1. Load last 3 `StatementDB` rows for the account, ordered by `uploaded_at DESC`.
2. If fewer than 2, return `[]` immediately (not enough signal).
3. For each statement, parse `recurring_candidates_json` and index by merchant name.
4. A merchant appearing in ≥2 of the 3 statements → `confirmed_recurring`.
5. Avg amount computed across appearances; sorted by `statement_count` descending.

**Endpoint:**
`GET /api/statements/recurring?account_number=XXXX` returns 200 (not 404) even when `confirmed_recurring` is empty. A new account with no history isn't an error — it just hasn't accumulated enough data yet.

**Schemas:**

```python
class ConfirmedRecurringItem(BaseModel):
    merchant: str
    statement_count: int
    avg_amount: float
    last_seen: str | None

class RecurringResponse(BaseModel):
    account_number: str
    confirmed_recurring: list[ConfirmedRecurringItem]
    requires_statements: int = 2
```

**Frontend — `SubscriptionsCard.tsx`:**

- Renders only when `subscriptions.length > 0`.
- Shows merchant name, statement count badge, avg amount.
- Monthly cost estimate: sum of all `avg_amount` values shown in the card header.

**`analyze.py` updated:**
After `detect_recurring(merchant_insights)` runs, the result is passed to `save_statement(..., recurring_candidates=recurring_candidates)`. This means the JSON stored per statement is always the BSA-07 lite output — cross-statement aggregation happens at query time, not at upload time.

**Tests — `test_recurring.py` (4 tests):**

- `test_cross_recurring_detected` — merchant in 2 statements → appears in confirmed list.
- `test_cross_recurring_single_statement` — only 1 statement → empty list.
- `test_cross_recurring_different_accounts` — same merchant, different accounts → each account sees nothing (cross-account isolation).
- `test_recurring_endpoint_returns_empty_not_404` — unknown account → 200 with empty list.

---

### 4. TD-007/008 — Analyzer Split

Before: `backend/app/models/analyzer.py` was ~1,280 lines with parsers, enrichers, scorers, and aggregators all in one class.

After:

| Module                            | Lines | Responsibility                                                                                                                                           |
| --------------------------------- | ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `parsers/excel_parser.py`         | 466   | `process_excel_csv()`, `detect_header_row()`, `find_column()`, `parse_amount()`, `normalize_date()`, `clean_column_name()`, `deduplicate_transactions()` |
| `parsers/pdf_parser.py`           | 286   | `process_pdf_transactions()`, `looks_like_header()`                                                                                                      |
| `enrichers/narration_enricher.py` | 271   | `analyze_narration_details()` — UPI/IMPS/NEFT/card regex extraction                                                                                      |
| `scorers/confidence_scorer.py`    | 32    | `calculate_confidence_score()` — penalty-based scorer                                                                                                    |
| `models/analyzer.py`              | 299   | `BankStatementAnalyzer` (thin orchestrator) + `TransactionPatternTrainer`                                                                                |

The split was purely internal — `BankStatementAnalyzer` stays importable from `app.models.analyzer`. The new modules import from each other where needed (pdf_parser imports `parse_amount`, `find_column`, `normalize_date`, `deduplicate_transactions` from excel_parser since they're shared). No test changes were needed — the external interface is unchanged.

**Why `analyzer.py` stayed above 300 lines:**
The plan said `< 300 lines` and it came in at 299. `TransactionPatternTrainer` (merchant aggregation, ~80 lines) stays in `analyzer.py` because it's conceptually close to the orchestration logic and didn't warrant its own module at this size.

---

## Key Decisions Made

### Why store `recurring_candidates_json` on `StatementDB` instead of re-deriving at query time?

The alternative would be to re-run `detect_recurring()` against all transactions for the account at query time. Storing wins because:

1. BSA-07 lite's `detect_recurring()` depends on `merchant_insights` (pre-aggregated), not raw transactions. Re-deriving it at query time would require fetching all transactions, running merchant aggregation, then running recurring detection — three hops instead of a JSON column read.
2. Storing freezes the state at upload time. This is correct: if thresholds change (e.g., CV is tuned from 0.25 to 0.20), older statements retain the detection that was run when they were uploaded.
3. The column is nullable and defaults to `[]`, so no migration risk on existing rows.

### Why `GET /api/statements/recurring` returns 200 (not 404) for unknown accounts?

A 404 would imply the endpoint itself wasn't found. An unknown account is a valid query with an empty result — semantically different. The `requires_statements: int = 2` field in the response communicates the threshold to the caller without them needing to read docs.

### Why `StaticPool` in test fixtures?

SQLite's in-memory databases (`:memory:`) are connection-scoped by default. FastAPI's dependency injection creates a new `Session` per request — a new connection — which sees an empty database. `StaticPool` forces all connections to share the same engine and therefore the same in-memory database. Every Sprint-05 test that combines `save_statement()` + HTTP client assertions uses `StaticPool`. This is a pattern worth carrying forward.

---

## What to Watch Out For

**`/api/statements/compare` route ordering:** Must be declared before `/{statement_id}/transactions` in `statements.py`. FastAPI path matching is first-wins. If the order is swapped, requests to `/compare` would try to cast `"compare"` to `int` and return 422. This is currently correct but fragile — adding a new named route below `/{id}` would silently break it.

**`recurring_candidates_json` stored at upload time:** If the CV threshold in `detect_recurring()` is tuned later, old statements won't automatically update. This is intentional (frozen state) but could confuse a future developer. The comment in `crud.py` should mention this.

**`top_category` in MoM response is nullable:** When a month has only CREDIT transactions (pure income, no debits), `category_totals` is empty and `top_category` is `None`. The frontend `MonthlyComparison.tsx` doesn't currently surface `top_category` — it only shows income/expense/net bars. That's fine for now, but when a category breakdown per month is added, `None` must be handled.

**Analyzer split created import coupling:** `pdf_parser.py` imports several functions from `excel_parser.py` (`parse_amount`, `find_column`, `normalize_date`, `deduplicate_transactions`). These are shared utilities that both parsers need. If `excel_parser.py` is ever renamed or those functions move, `pdf_parser.py` breaks. A `parsers/utils.py` extraction would eliminate this coupling — a Sprint-06 or later refactor opportunity.

---

## What's Next

The Sprint-06 roadmap (from `sprint-05-plan.md` P2 backlog):

| Ticket | Description                                                                       |
| ------ | --------------------------------------------------------------------------------- |
| BSA-06 | Natural-language Q&A over transaction history (RAG or tool-calling over SQLite)   |
| BSA-16 | Category-correction learning loop (uses `corrections` table already in the DB)    |
| BSA-20 | Statement history UI — browse past statements, reload from DB, delete old entries |
| BSA-21 | Budget/alert thresholds per category                                              |
| TD-018 | `TransactionTable` virtualization before history inflates row counts              |
| TD-019 | Docker + docker-compose                                                           |
| TD-023 | Magic-byte upload validation                                                      |
| TD-025 | `transaction_reference` regex too greedy                                          |

BSA-06 (natural-language Q&A) is the headline Sprint-06 feature — it leverages all the persistence infrastructure the last two sprints built. The corrections loop (BSA-16) is the highest-leverage improvement to data quality. History UI (BSA-20) closes the loop on showing users what they've uploaded. These three together would make the product feel genuinely longitudinal rather than upload-by-upload.

---

_Prev: `docs/study/sprint-04-learnings.md` · Plan: `docs/sprint-05-plan.md` · Debt: `docs/tech-debt.md`_
