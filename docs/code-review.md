# Code Review — Bank Statement Analyzer

**Reviewed by:** Claude (Cowork)  
**Current review:** Sprint-05 (BSA-17 MoM comparison, BSA-07-full cross-statement recurring, TD-007/008 analyzer split, CR-S4 housekeeping)  
**Review date:** 2026-06-22  
**Scope:** Month-over-month comparison endpoint + frontend, cross-statement recurring detection, monolithic analyzer split into modules, housekeeping block.

> Previous review (`Sprint-04`) is summarized at the bottom. Full text in git history.

---

## Sprint-05 Completion Check

| Task                                               | Shipped? | Notes                                                                                |
| -------------------------------------------------- | -------- | ------------------------------------------------------------------------------------ |
| CR-S4-01 — Pagination on `GET /api/statements`     | ✅       | `limit`/`offset` query params; default limit=20, max 100                             |
| CR-S4-02 — `GET /api/statements/{id}/transactions` | ✅       | Typed response, paginated (default 100, max 500), 404 on unknown                     |
| CR-S4-03 — CorrectionDB fingerprint comment        | ✅       | Comment in `crud.py` documents key format for BSA-16                                 |
| CR-S4-05 — Export filename sanitization            | ✅       | `re.sub(r"[^\w\-.]", "_", req.filename)` before Content-Disposition                  |
| BSA-17 — Month-over-month comparison               | ✅       | `GET /api/statements/compare`, `MonthlyComparison.tsx`, 4 tests                      |
| BSA-07-full — Cross-statement recurring            | ✅       | `GET /api/statements/recurring`, Alembic migration, `SubscriptionsCard.tsx`, 4 tests |
| TD-007/008 — Analyzer split                        | ✅       | 4 focused modules; `analyzer.py` now 299 lines (was ~1,280)                          |

**Net:** All P0 and P1 items shipped. Test count grew from ~38 to ~46. The product now has meaningful longitudinal intelligence: two users who've uploaded Jan/Feb/Mar can see a trend chart and confirmed subscriptions.

---

## Sprint-05 Findings

### CR-S5-01 🟡 `GET /api/statements/compare` route ordering is fragile

**File:** `backend/app/routers/statements.py`

`/api/statements/compare` must appear before `/{statement_id}/transactions` in the router. FastAPI matches routes top-to-bottom and would try to cast `"compare"` to `int` if the order is swapped. Currently correct, but any new named route added after this block must be inserted above `/{statement_id}`, not below it. Consider adding a comment in the file.

**Severity:** Low (currently safe, risk is future edit)  
**Recommendation:** Add `# NOTE: named routes (/compare, /recurring) must stay above /{statement_id}` above the parametric route.

---

### CR-S5-02 🟡 `top_category` in `MonthSummary` is not surfaced in the frontend

**File:** `backend/app/models/schemas.py`, `frontend/components/MonthlyComparison.tsx`

`MonthSummary` computes `top_category` per month and returns it in the API response, but `MonthlyComparison.tsx` doesn't render it. The chart shows income/expense/net bars and a compact tile row (expenses only). The per-month top category would add value — "January: ₹12k expenses / Food & Dining" is a more useful summary tile than a bare expense figure.

**Severity:** Low (feature gap, not a defect)  
**Recommendation:** Add a small `top_category` label below each expense figure in the tile row. One line change in the frontend.

---

### CR-S5-03 🟢 `pdf_parser.py` imports utility functions from `excel_parser.py`

**File:** `backend/app/parsers/pdf_parser.py` lines 4–11

```python
from app.parsers.excel_parser import (
    clean_column_name,
    deduplicate_transactions,
    find_column,
    normalize_date,
    parse_amount,
)
```

These five functions are shared utilities needed by both parsers. Importing them from `excel_parser` works but creates an implicit "excel is the source of truth for shared parsing utils" coupling. If `excel_parser.py` is ever restructured, `pdf_parser.py` breaks silently.

**Severity:** Low  
**Recommendation:** Extract shared utilities to `parsers/utils.py` in a future sprint. Not urgent — the coupling is explicit and visible, just not well-named.

---

### CR-S5-04 🟢 `recurring_candidates_json` staleness not documented in code

**File:** `backend/app/db/crud.py` — `save_statement()`

The `recurring_candidates_json` column stores BSA-07 lite output at upload time. If the CV threshold or count minimum in `detect_recurring()` is tuned later, re-uploaded statements will get new candidate lists but existing rows keep the old ones. This is intentional (frozen-state design) but no comment says so. A future developer might try to "refresh" these lists by re-querying and be confused.

**Severity:** Low (documentation gap)  
**Recommendation:** Add a one-line comment: `# Frozen at upload time. Re-upload statement to refresh recurring detection.`

---

### CR-S5-05 🟠 `get_monthly_summary` fetches all transactions per statement without a limit

**File:** `backend/app/db/crud.py` — `get_monthly_summary()`

```python
txns = session.exec(
    select(TransactionDB).where(TransactionDB.statement_id == stmt.id)
).all()
```

No limit. A statement with 2,000 transactions loads all 2,000 into memory per comparison query. For a single user with 3 statements of 500 txns each, this is ~1,500 objects — fine today. If statement counts grow (BSA-20 history UI), or if someone uploads large multi-month exports, this becomes a linear memory spike per compare call.

**Severity:** Medium (latent, not urgent today but will bite)  
**Recommendation:** Add a practical cap (`select(...).limit(5000)`) or stream in batches. The aggregation loop is simple enough that batching adds minimal complexity.

---

### CR-S5-06 🟢 `MonthlyComparison.tsx` YAxis formatter assumes INR thousands only

**File:** `frontend/components/MonthlyComparison.tsx`

```tsx
tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
```

Divides all values by 1,000 regardless of magnitude. A statement with very small amounts (₹50 transactions, ₹500 balance) produces ticks like `₹0k`, `₹0k`. A statement with very large amounts (₹500k salary) produces `₹500k` which is fine, but anything under ₹1,000 reads as `₹0k`.

**Severity:** Low (cosmetic, affects low-value statements)  
**Recommendation:** Use a conditional formatter: values ≥1,000 → `₹Xk`, values < 1,000 → `₹X`.

---

### CR-S5-07 🟡 `SubscriptionsCard.tsx` monthly cost estimate assumes all subscriptions are monthly

**File:** `frontend/components/SubscriptionsCard.tsx`

```tsx
const monthlyTotal = subscriptions.reduce((sum, s) => sum + s.avg_amount, 0);
```

Sums `avg_amount` across all confirmed recurring merchants and labels it "/mo". A quarterly charge (tax payment, insurance premium) or annual subscription would inflate the monthly estimate. The detection window is 3 statements, so the estimate is based on whatever cadence happened to appear — it might be monthly, bi-monthly, or random.

**Severity:** Low (UX accuracy, not a bug)  
**Recommendation:** Either add a caveat ("Est. based on detected frequency") or display individual items without a total sum until cadence detection is added.

---

## Summary

Sprint-05 is structurally the cleanest sprint so far. The analyzer split is a genuine improvement — `models/analyzer.py` at 299 lines versus the 1,280-line monolith is a meaningful difference for readability and testability. The two longitudinal endpoints (compare, recurring) are well-tested, the schemas are correct, and the frontend components are functional.

Seven findings total: one medium (CR-S5-05 — unbounded query in `get_monthly_summary`), three low-severity structural observations (CR-S5-01/03/04), and three UX/cosmetic items (CR-S5-02/06/07). None are regressions; all are forward-looking improvements.

The highest-priority fix before Sprint-06 is CR-S5-05 (add a query limit in `get_monthly_summary`) since Sprint-06 adds the history UI (BSA-20) which will increase statement counts and make this call more frequent.

---

## Sprint-04 Summary (previous)

**Reviewed:** BSA-19 (SQLite persistence), TD-024 (row-level dedup), BSA-13 (CSV/Excel export), BSA-07 lite (recurring detection MVP), TD-038/039/040/041 (housekeeping).

**Findings carried forward:**

- CR-S4-01 ✅ — pagination on `GET /api/statements` → fixed in Sprint-05 housekeeping
- CR-S4-02 ✅ — `GET /api/statements/{id}/transactions` endpoint → added in Sprint-05
- CR-S4-03 ✅ — CorrectionDB fingerprint comment → added in Sprint-05
- CR-S4-05 ✅ — export filename sanitization → fixed in Sprint-05

All Sprint-04 CR items closed in Sprint-05 housekeeping block.

---

## Sprint-04 Completion Check

| Task                                      | Shipped? | Notes                                                                                     |
| ----------------------------------------- | -------- | ----------------------------------------------------------------------------------------- |
| TD-039 — `insights` in `AnalysisResult`   | ✅       | Already present from Sprint-03; confirmed by reading schemas.py                           |
| TD-040 — `currency` in `SummaryResponse`  | ✅       | Already present from Sprint-03; confirmed by reading schemas.py                           |
| TD-041 — backend-v2 → backend rename      | ✅       | CLAUDE.md cleaned; all `backend-v2` references removed                                    |
| TD-038 — AI badge on enriched rows (full) | ✅       | New "Category" column in TransactionTable; indigo "AI" pill with `title="AI-categorized"` |
| BSA-19 — SQLite persistence layer         | ✅       | `app/db/` package, Alembic migration, `persist=true` flag, `GET /api/statements`          |
| TD-024 — Row-level transaction dedup      | ✅       | `_deduplicate_transactions()` — compound key, before confidence scoring, 7 tests          |
| BSA-13 — CSV / Excel export               | ✅       | `POST /api/export/transactions`, StreamingResponse, "↓ CSV" + "↓ Excel" buttons           |
| BSA-07 lite — Recurring detection         | ✅       | `detect_recurring()`, `recurring_candidates` in schema, ↻ pill in merchant table          |

**Net:** A complete sprint. All P0 items shipped; both P1 items pulled forward and shipped. The product is no longer stateless. Test count grew from 18 to ~38.

---

## Summary

Sprint-04 is the most architecturally significant sprint so far. Persistence is live, dedup is two-layered (file-hash + row-level), and the export path is clean (streaming, no temp files). The code quality is consistent with the previous sprint — the db package is well-structured, the crud functions are isolated, and the test coverage for the new code is solid. Issues found are low-severity; none block Sprint-05.

---

## What Looks Good

**`app/db/` package structure is clean.** Three-file split (`database.py`, `models.py`, `crud.py`) maps exactly to three concerns: engine/session, table definitions, and write logic. A future developer can find any persistence concern in one obvious file.

**Pydantic and SQLModel models are kept separate.** `StatementDB`/`TransactionDB` are in `db/models.py`; `Transaction`/`AccountInfo` stay in `schemas.py`. This avoids the well-known footgun where `table=True` modifies field ordering and breaks Pydantic validators.

**`save_statement()` uses `flush()` before writing transactions.** `session.flush()` populates `stmt.id` within the transaction without committing. This means all rows land in a single commit — either all of them succeed or none do. Clean atomicity.

**The `persist=true` flag is truly additive.** Tests that hit `/api/analyze/bank/statement` without the flag continue to work without any DB setup. The stateless path is unchanged. Sprint-04's test for `persist=true` confirms this by using a separate DB fixture.

**`_deduplicate_transactions()` runs at the right point.** After extraction, before confidence scoring. Duplicates never reach the scorer and never reach the DB. The compound key `(date, amount, narration[:100], balance)` is the right fingerprint for bank rows — more than just `(date, amount)` (catches legitimate same-day same-amount transactions) but not the full narration (avoids false-uniqueness on whitespace variation).

**Export uses StreamingResponse with no temp files.** The `BytesIO`/`StringIO` approach avoids the `uploads/` accumulation problem flagged in Sprint-01. The `openpyxl` auto-fit with a 50-char cap is a thoughtful UX detail.

**CV threshold raise from 0.15 → 0.25 is the right call.** The CR-S3-01 finding from the Sprint-03 review was acted on. The new threshold catches real-world subscriptions with minor price variation while still filtering genuinely irregular merchants.

**`detect_recurring()` is a pure function.** No side effects, easily testable, returns a stable sorted list. Four tests cover all the cases — detected (CV low), excluded (CV high), excluded (count < 3), excluded (UNKNOWN/OTHER).

---

## Issues Found

### CR-S4-01 🟡 `GET /api/statements` has no pagination — future scalability concern

**File:** `backend/app/routers/statements.py`  
**Severity:** 🟡 Medium (not a problem now; will be at scale)

```python
statements = session.exec(
    select(StatementDB).order_by(StatementDB.uploaded_at.desc())
).all()
```

`.all()` fetches every row. For a personal tool uploading a few statements a month, this is negligible. At 100+ uploads, this query returns the full history payload on every page load. Add `limit` / `offset` query params before the history UI is wired in Sprint-05:

```python
@router.get("/api/statements")
def list_statements(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
    session: Session = Depends(get_session),
):
```

---

### CR-S4-02 🟡 `GET /api/statements/{id}/transactions` endpoint is missing

**File:** `backend/app/routers/statements.py` (gap — endpoint not yet added)  
**Severity:** 🟡 Medium (blocks Sprint-05 history UI)

The ADR and Sprint-04 plan both mention `GET /api/statements/{id}/transactions` as the detail endpoint for pulling a specific statement's transaction payload. `StatementDB.id` and `TransactionDB.statement_id` FK are in place, but there's no router handler. Sprint-05's month-over-month comparison and history view will need this. Add it as a first commit of Sprint-05:

```python
@router.get("/api/statements/{statement_id}/transactions")
def get_statement_transactions(statement_id: int, session: Session = Depends(get_session)):
    txns = session.exec(
        select(TransactionDB).where(TransactionDB.statement_id == statement_id)
    ).all()
    if not txns:
        raise HTTPException(status_code=404, detail="Statement not found or empty")
    return {"transactions": [t.model_dump() for t in txns]}
```

---

### CR-S4-03 🟢 `CorrectionDB` has no write path yet — fingerprint format undocumented

**File:** `backend/app/db/models.py`, `backend/app/db/crud.py`  
**Severity:** 🟢 Low (intentional deferral — BSA-16 will wire it)

`CorrectionDB` is in the schema and Alembic migration. But `save_correction()` and the correction fingerprint format (SHA-256 of what exactly?) aren't defined. For BSA-16 to work, the fingerprint needs a clear, documented spec before implementation. Recommendation: add a comment in `crud.py`:

```python
# CorrectionDB fingerprint: SHA-256 of f"{transaction_date}:{amount}:{narration[:100]}"
# Must match the key used in the learning loop (BSA-16).
```

---

### CR-S4-04 🟢 `TransactionDB.category` stored as JSON string — no constraint or validation

**File:** `backend/app/db/models.py`  
**Severity:** 🟢 Low (consistency concern)

```python
category: Optional[str] = None  # JSON-encoded list: '["Food & Dining"]'
```

A comment documents the intent, but there's nothing preventing a caller from writing a plain string (e.g., `"Food & Dining"`) instead of a JSON list. `crud.py` currently uses `json.dumps(txn.get("category") or [])` correctly. Add a note in `crud.py` or a small validator to catch this if/when more write paths open up.

---

### CR-S4-05 🟢 Export `filename` parameter is unsanitized in `Content-Disposition` header

**File:** `backend/app/routers/export.py`  
**Severity:** 🟢 Low (minor — personal tool, no auth surface)

```python
headers={"Content-Disposition": f'attachment; filename="{req.filename}.csv"'}
```

If a client passes a path-traversal string, it would appear verbatim in the header. The browser uses this for the save dialog, not for disk paths, so the blast radius is cosmetic. One-line fix:

```python
import re
safe_name = re.sub(r"[^\w\-.]", "_", req.filename)
```

---

## Suggestions (Style / Cleanup)

| #        | File                        | Suggestion                                                                                                                                                                        |
| -------- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CR-S4-06 | `db/database.py`            | Add a module-level docstring explaining engine lifetime (singleton at import time) and the in-memory SQLite override used in tests.                                               |
| CR-S4-07 | `tests/test_persistence.py` | Confirm `db_session` fixture uses `Session` from `sqlmodel` (not raw SQLAlchemy `sessionmaker`) to match the production path exactly.                                             |
| CR-S4-08 | `routers/analyze.py`        | The `if persist:` branches live inline in the route handler. Consider a thin `PersistenceService` wrapper — makes the handler easier to read and easier to mock in tests.         |
| CR-S4-09 | `conftest.py`               | `sample_transactions_payload` has 3 minimal transactions. Add one with `llm_enriched: True` and one with a non-empty `category` list — export tests should exercise those fields. |
| CR-S4-10 | `routers/statements.py`     | Add a `GET /api/statements/{id}` single-record endpoint alongside the list endpoint — useful for debug and for the future history UI.                                             |

---

## Verdict

**Approve.** Sprint-04 shipped cleanly. The persistence layer is architecturally sound, dedup is two-layered and correct, export is streaming and clean, and recurring detection is well-tested. Issues found are all low/medium severity and are either planned Sprint-05 work (CR-S4-02 missing endpoint) or minor defensive improvements. None block Sprint-05.

**Priority items for Sprint-05 first commit:**

1. `GET /api/statements/{id}/transactions` — Sprint-05 history UI is blocked without it (CR-S4-02)
2. Pagination on `GET /api/statements` — 5 minutes, unblocks safe scaling (CR-S4-01)

---

## Carried Issues (still open from previous sprints)

- **TD-007** — `BankStatementAnalyzer` is ~1,300 lines. Sprint-05 should split it before more parsers are added.
- **TD-008** — Column detection duplicated across Excel/PDF paths. Pair with TD-007.
- **TD-018** — `TransactionTable` renders all rows with no virtualization. More urgent now that persistence makes multi-statement history possible.
- **TD-019** — No Docker/docker-compose. Unblocked since Flask deletion.
- **TD-023** — Upload validation trusts extension, not magic bytes.
- **TD-025** — `transaction_reference` fallback regex too greedy.
- **TD-026** — Confidence penalizes balance-less formats unconditionally.

---

## Appendix — Sprint-03 Review (archived)

Sprint-03 review covered TD-033/034/035/036/037, CR-S2-08 (category taxonomy), BSA-12/15 (spending card + insights strip), BSA-18 (Flask deletion + CI), and ADR-002. Its findings CR-S3-01 through CR-S3-05 were **all resolved in Sprint-04**. CV threshold fix (CR-S3-01) landed in BSA-07 lite; all schema/badge items resolved in housekeeping. Full text in git history.

---

_Tech debt: `docs/tech-debt.md` · Testing: `docs/testing-strategy.md` · Study: `docs/study/sprint-04-learnings.md` · Sprint plan: `docs/sprint-05-plan.md`_
