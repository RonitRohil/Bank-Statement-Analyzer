# Code Review — Bank Statement Analyzer

**Reviewed by:** Claude (Cowork)  
**Current review:** Sprint-04 (BSA-19 persistence, TD-024 dedup, BSA-13 export, BSA-07 lite recurring, TD-038/039/040/041 housekeeping)  
**Review date:** 2026-06-21  
**Scope:** SQLite/SQLModel persistence layer, transaction deduplication, CSV/Excel export, recurring detection, schema fixes, and AI badge.

> Previous review (`Sprint-03`) is summarized at the bottom. Full text in git history.

---

## Sprint-04 Completion Check

| Task | Shipped? | Notes |
|------|----------|-------|
| TD-039 — `insights` in `AnalysisResult` | ✅ | Already present from Sprint-03; confirmed by reading schemas.py |
| TD-040 — `currency` in `SummaryResponse` | ✅ | Already present from Sprint-03; confirmed by reading schemas.py |
| TD-041 — backend-v2 → backend rename | ✅ | CLAUDE.md cleaned; all `backend-v2` references removed |
| TD-038 — AI badge on enriched rows (full) | ✅ | New "Category" column in TransactionTable; indigo "AI" pill with `title="AI-categorized"` |
| BSA-19 — SQLite persistence layer | ✅ | `app/db/` package, Alembic migration, `persist=true` flag, `GET /api/statements` |
| TD-024 — Row-level transaction dedup | ✅ | `_deduplicate_transactions()` — compound key, before confidence scoring, 7 tests |
| BSA-13 — CSV / Excel export | ✅ | `POST /api/export/transactions`, StreamingResponse, "↓ CSV" + "↓ Excel" buttons |
| BSA-07 lite — Recurring detection | ✅ | `detect_recurring()`, `recurring_candidates` in schema, ↻ pill in merchant table |

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

| # | File | Suggestion |
|---|------|-----------|
| CR-S4-06 | `db/database.py` | Add a module-level docstring explaining engine lifetime (singleton at import time) and the in-memory SQLite override used in tests. |
| CR-S4-07 | `tests/test_persistence.py` | Confirm `db_session` fixture uses `Session` from `sqlmodel` (not raw SQLAlchemy `sessionmaker`) to match the production path exactly. |
| CR-S4-08 | `routers/analyze.py` | The `if persist:` branches live inline in the route handler. Consider a thin `PersistenceService` wrapper — makes the handler easier to read and easier to mock in tests. |
| CR-S4-09 | `conftest.py` | `sample_transactions_payload` has 3 minimal transactions. Add one with `llm_enriched: True` and one with a non-empty `category` list — export tests should exercise those fields. |
| CR-S4-10 | `routers/statements.py` | Add a `GET /api/statements/{id}` single-record endpoint alongside the list endpoint — useful for debug and for the future history UI. |

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
