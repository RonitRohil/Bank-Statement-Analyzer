# Sprint-04 Learnings — "The Database Decision Was Made. Build It."

**Sprint dates:** 2026-06-21  
**Status:** Complete  
**Theme:** Turn the stateless parser into a stateful financial record

---

## What Was Built

Sprint-04 delivered five distinct pieces. Three were P0 (must-ship); two were P1 (capacity-permitting). All five shipped.

| Ticket | What shipped | Files touched |
|--------|-------------|---------------|
| TD-038/039/040/041 | Housekeeping block — schema fields, AI badge, backend rename | `schemas.py`, `TransactionTable.tsx`, `CLAUDE.md` |
| BSA-19 | SQLite persistence via SQLModel + Alembic | `backend/app/db/`, `alembic/`, `routers/statements.py`, `routers/analyze.py` |
| TD-024 | Row-level transaction deduplication inside parser | `analyzer.py`, `tests/test_dedup.py` |
| BSA-13 | CSV / Excel export endpoint + frontend download buttons | `routers/export.py`, `api.ts`, `TransactionTable.tsx` |
| BSA-07 lite | Single-statement recurring detection with `recurring_candidates` field | `insights.py`, `schemas.py`, `MerchantInsights.tsx` |

Test count grew from 18 → ~38 tests (6 new persistence, 7 new dedup, 3 new export, 4 new recurring detection tests).

---

## Why It Was Built

Sprint-03 closed the loop on what Sprint-02 started: the enricher worked, the summary card was visible, Flask was gone. But the whole product was still stateless — every upload was its own island. No history. No dedup. No way to ask "how does this month compare to last month?"

The sprint-03 ADR made the call: SQLite via SQLModel, three-table schema. Sprint-04's job was mechanical: implement what the design said.

The housekeeping block existed because Sprint-03's code review found four items that could be fixed in a single commit — two schema fields that were already in the code but not in the Pydantic models, an old directory reference in CLAUDE.md, and a half-built AI badge in the transaction table. These were the first commit of the sprint.

The two P1 items (export, recurring detection) were pulled forward because Sprint-04 finished ahead of schedule. Export is the single most-requested thing people want from a PDF parser — get the data *out*. Recurring detection was a natural complement to the merchant insights already in the response.

---

## How It Works

### 1. Housekeeping (TD-038/039/040/041)

Commit-one changes verified by reading `schemas.py` first:
- `AnalysisResult` already had `insights: List[str] = []` (Sprint-03 BSA-15 had added it). No change needed.
- `SummaryResponse` already had `currency: str = "INR"`. No change needed.
- The `backend-v2/` rename to `backend/` was already done on disk. Cleaned up 6 stale references in CLAUDE.md.
- **AI badge (TD-038 full):** Added a "Category" column to `TransactionTable.tsx`. When `txn.llm_enriched === true`, an indigo `"AI"` pill with `title="AI-categorized"` renders inline. Rows with no category show `—`. The previous partial implementation (wrong column, wrong color, no `title`) was removed.

### 2. BSA-19 — SQLite Persistence

**Three-layer design** (all in `backend/app/db/`):

```
database.py  — engine creation, get_session FastAPI dependency, create_db_and_tables()
models.py    — StatementDB, TransactionDB, CorrectionDB SQLModel table models
crud.py      — hash_file(), find_statement_by_hash(), save_statement()
```

**Three tables:**

- `statements` — one row per uploaded file. Keyed by `file_hash` (SHA-256 of file bytes) for dedup. Stores account metadata, period, confidence score.
- `transactions` — one row per parsed transaction, FK to `statements.id`. Stores all enriched fields; `category` is JSON-encoded `'["Food & Dining"]'` since SQLite has no array column type.
- `corrections` — one row per user category correction (fingerprint-keyed). Reserved for BSA-16's learning loop. Schema is in place; no write path yet.

**The `persist=true` toggle** in `POST /api/analyze/bank/statement`:

```python
@router.post("/api/analyze/bank/statement")
async def analyze(
    file: UploadFile,
    persist: bool = Query(default=False),
    session: Session = Depends(get_session),
):
    file_bytes = await file.read()
    file_hash = hash_file(file_bytes)

    if persist:
        existing = find_statement_by_hash(session, file_hash)
        if existing:
            # return cached JSON — no re-parse
            return cached_response(existing, session)

    # ... run parser ...

    if persist:
        save_statement(session, file_hash, file.filename, result)

    return result
```

The stateless path (no `persist` flag) is identical to pre-Sprint-04. The flag is additive — no existing behavior changes.

**Alembic:**

```
backend/alembic/
    alembic.ini
    env.py          ← imports SQLModel metadata; uses DATABASE_URL from settings
    versions/
        9670b8f28c89_initial.py   ← creates statements, transactions, corrections
```

Migration runs with `alembic upgrade head`. Tests use an in-memory SQLite session fixture — no migration needed, `create_db_and_tables()` handles schema for tests.

**`GET /api/statements`** returns all stored statements ordered by `uploaded_at DESC`:

```json
{
  "statements": [
    {
      "id": 1,
      "file_hash": "a3f...",
      "original_filename": "hdfc-june.pdf",
      "bank_name": "HDFC",
      "account_number": "50100...",
      "period_from": "2026-06-01",
      "period_to": "2026-06-30",
      "uploaded_at": "2026-06-21T...",
      "confidence_overall": 0.94
    }
  ]
}
```

**Encryption decision:** No encryption at rest for this sprint. The `.db` file contains real financial data (account numbers, amounts, narrations). Users are responsible for OS-level full-disk encryption. Must be revisited before any networked or multi-user deployment. Documented in ADR-002 footnote and CLAUDE.md deployment notes.

### 3. TD-024 — Row-Level Transaction Deduplication

`BankStatementAnalyzer._deduplicate_transactions(transactions: list[dict]) -> list[dict]`

Compound key: `(transaction_date, amount, narration[:100], balance)`

```python
def _deduplicate_transactions(self, transactions):
    seen = set()
    result = []
    for txn in transactions:
        key = (
            txn.get("transaction_date"),
            txn.get("amount"),
            (txn.get("narration") or "")[:100],
            txn.get("balance"),
        )
        if key not in seen:
            seen.add(key)
            result.append(txn)
        else:
            logger.info(f"[DEDUP] Dropped duplicate: {key}")
    return result
```

Called **after** extraction, **before** confidence scoring — in both `_process_excel_csv()` and `_process_pdf_transactions()`. Logs at INFO only when duplicates are actually dropped (no log noise on clean statements).

Two layers of dedup now exist:
- **File-level** (BSA-19): SHA-256 `file_hash` on `StatementDB` — prevents re-parsing the same file upload
- **Row-level** (TD-024): `_deduplicate_transactions` — handles the multi-page PDF boundary-row overlap problem (TD-021 stitching could extract the same row from two adjacent pages)

### 4. BSA-13 — CSV / Excel Export

**Backend: `POST /api/export/transactions`** in `backend/app/routers/export.py`

Request body:
```json
{
  "transactions": [...],
  "format": "csv",     // or "xlsx"
  "filename": "transactions"
}
```

- Empty transactions list → 400 (validated before building the DataFrame)
- CSV: `pd.DataFrame.to_csv()` → `StreamingResponse(iter([...]), media_type="text/csv")`
- XLSX: `pd.ExcelWriter(output, engine="openpyxl")` → auto-fits column widths (capped at 50 chars) → `StreamingResponse`
- No temp files written to disk — everything streams from memory
- Multi-category lists joined with `", "` for human readability

**Frontend:**

`exportTransactions(transactions, format)` in `api.ts`:
1. `POST /api/export/transactions` with `Content-Type: application/json`
2. Response as `blob()`
3. `URL.createObjectURL(blob)` → anchor click → `revokeObjectURL` cleanup

`TransactionTable.tsx` header row:
```tsx
<button onClick={() => handleExport("csv")} disabled={exporting || !transactions.length}>
  ↓ CSV
</button>
<button onClick={() => handleExport("xlsx")} disabled={exporting || !transactions.length}>
  ↓ Excel
</button>
```

Buttons disabled during export and when transaction list is empty. Loading state prevents double-clicks.

### 5. BSA-07 Lite — Single-Statement Recurring Detection

`detect_recurring(merchant_insights: dict) -> list[dict]` in `backend/app/services/insights.py`

Criteria:
- `count >= 3` — needs to appear at least three times
- `cv = std_amount / avg_amount < 0.25` — amounts are consistent
- Not "UNKNOWN" / "OTHER" — named merchants only

Returns sorted by count descending. Each entry:
```json
{
  "merchant": "NETFLIX",
  "count": 3,
  "avg_amount": 649.0,
  "std_amount": 0.0,
  "cv": 0.0,
  "first_seen": "2026-06-01",
  "last_seen": "2026-06-28",
  "common_days": [1, 28]
}
```

**CV threshold raised from 0.15 → 0.25** (CR-S3-01 fix): Real-world subscriptions sometimes vary slightly (FX fluctuation on streaming services, occasional telecom data charges). 0.15 was too tight and silently excluded legitimate recurring merchants.

**Schema:** `recurring_candidates: List[Dict[str, Any]] = []` added to `AnalysisResult`. Defaults to empty so existing callers/tests are unaffected.

**Frontend:** `MerchantInsights.tsx` builds a `Set<string>` from `recurringCandidates` merchant names. Any matching merchant card gets a `↻` green pill:
```tsx
{recurringSet.has(m.merchant) && (
  <span className="text-green-600 ml-1" title="Likely recurring">↻</span>
)}
```

---

## Key Decisions Made

### Why `persist=true` as a query param, not a config toggle

The ADR considered both. A query param keeps the stateless path entirely unchanged — no settings change, no restart, just omit the flag. Config toggles require restarting the server for the same effect and make the stateless path less obvious in tests. The flag also enables the frontend to offer a "Save this statement" option in the future.

### Why separate Pydantic and SQLModel models

Pydantic models (`Transaction`, `AccountInfo` in `schemas.py`) are the API boundary — they handle request/response validation. SQLModel table models (`StatementDB`, `TransactionDB` in `db/models.py`) are the DB boundary. Mixing them means SQLModel's `table=True` metaclass modifies the model in ways that break pure Pydantic use (field ordering, validators). Keeping them separate means both can evolve independently.

### Why `category` is JSON-encoded string in `TransactionDB`

SQLite has no native array type. Options were: (1) a separate `transaction_categories` junction table, (2) comma-separated string, (3) JSON-encoded list. JSON preserves type and is easily decoded. Junction tables add query complexity for a field that's read as a unit, never filtered by individual category in this sprint. Can be normalized later.

### Why streaming response for export (no temp files)

The export endpoint builds the CSV/XLSX in memory (`StringIO`/`BytesIO`) and streams it. Writing to a temp file would require cleanup logic (the same problem the original Flask controller had with `uploads/` growing unbounded). Memory approach is cleaner for bank statement sizes (< 1MB even at 1,000 transactions).

### Why CV < 0.25 and not CV < 0.15

0.15 means std must be < 15% of mean. Empirically, subscriptions with even minor price variation (USD to INR, data add-ons, tax-inclusive vs. exclusive) had CVs of 0.16–0.24. At 0.25, a subscription must stay within ~25% of its average amount — still tight enough to exclude clearly irregular merchants.

---

## What to Watch Out For

### 1. The `statements.db` file grows without bound
Every `persist=true` upload writes rows to SQLite. No retention policy, no delete endpoint. For a personal tool this is fine for months. If statements are uploaded daily it will accumulate years of data. Document this in the README and add a CLI cleanup command in Sprint-05 or later.

### 2. `GET /api/statements` returns no transactions
The endpoint returns the `StatementDB` row metadata only — no transaction payload. The ADR defined `GET /api/statements/{id}/transactions` as a separate endpoint for the transaction detail. This endpoint does not exist yet. Sprint-05 should add it before the frontend tries to use it for history views.

### 3. `CorrectionDB` table exists but has no write path
The `corrections` table is in the schema and Alembic migration. `CorrectionDB` is imported but `save_correction()` doesn't exist yet. BSA-16 will wire this. Until then, the table is inert.

### 4. Row-level dedup uses narration[:100] — long narrations could false-positive differ
The 100-char truncation is defensive (keeps the key size manageable). Two transactions with identical first 100 chars of narration but different tails would be incorrectly deduped. In practice this doesn't happen with bank narrations (they're short and structured), but it's a latent edge case.

### 5. Export endpoint is `POST`, not `GET`
The transactions payload can't be in a query string (too large). The `POST /api/export/transactions` takes the full transactions JSON body. This means "download" requires a JS-triggered POST + blob — which is what `exportTransactions()` does. Caveat: this pattern doesn't work if JavaScript is disabled or in non-browser contexts. For a React app this is fine.

### 6. Alembic `env.py` uses `settings.database_url` — must match startup
`create_db_and_tables()` (for tests) and `alembic upgrade head` (for migration) both need to point at the same database. If `DATABASE_URL` env var is not set, both default to `sqlite:///./statements.db` relative to the CWD. Running Alembic from a different directory than uvicorn creates two separate `.db` files. Document: always run `alembic` from `backend/`.

---

## What's Next

Sprint-05 unlocks the features that were gated on persistence:

- **BSA-17 — Month-over-month comparison:** Pull multiple `StatementDB` rows for the same account, aggregate transactions by month, surface delta charts and percentage changes. Requires `GET /api/statements/{id}/transactions` (see gap above).
- **BSA-07-full — Cross-statement recurring detection:** Compare `recurring_candidates` JSON across statement rows for the same `account_number`. Higher confidence signal than single-statement detection.
- **TD-007/008 — Analyzer split:** `BankStatementAnalyzer` is ~1,300 lines. Before adding more parsers (OCR, new bank formats), split into `parsers/excel_parser.py`, `parsers/pdf_parser.py`, `enrichers/narration_enricher.py`, `scorers/confidence_scorer.py`. This is the parser extensibility prerequisite.
- **`GET /api/statements/{id}/transactions`** — Essential for the history UI to work. Simple CRUD query on `TransactionDB` filtered by `statement_id`.

---

*Architecture: `docs/adr-002-persistence.md` · Code review: `docs/code-review.md` · Tech debt: `docs/tech-debt.md` · Sprint plan: `docs/sprint-05-plan.md`*
