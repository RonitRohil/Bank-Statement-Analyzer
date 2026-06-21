# Sprint-05 Prompt 04 — Split Monolithic Analyzer (TD-007/008)

**Tickets:** TD-007, TD-008  
**Estimated time:** 3–4h  
**Priority:** P1 (do if prompts 01 and 02 are complete and capacity remains)  
**Context:** `docs/tech-debt.md` (TD-007/008), `docs/sprint-05-plan.md`

`BankStatementAnalyzer` in `backend/app/models/analyzer.py` is ~1,300 lines. Before adding more parsers (OCR, new bank formats, CSV dialect variations), split it into focused modules. This is a pure internal refactor — external API and all existing tests must remain unchanged.

---

## Files to Read First

- `backend/app/models/analyzer.py` — the full file (read it completely before writing anything)
- `backend/app/routers/analyze.py` — how `AnalyzeModel` is imported and called
- `backend/tests/test_analyze.py` — existing tests that must stay green
- `backend/tests/test_dedup.py` — tests for `_deduplicate_transactions`

---

## Target Structure

```
backend/app/
    parsers/
        __init__.py
        excel_parser.py     ← _process_excel_csv() + detect_header_row() + find_column() + parse_amount() + normalize_date()
        pdf_parser.py       ← _process_pdf_transactions() + _looks_like_header()
    enrichers/
        __init__.py
        narration_enricher.py   ← analyze_narration_details() + supporting regex dicts
    scorers/
        __init__.py
        confidence_scorer.py    ← calculate_confidence_score()
    models/
        analyzer.py         ← BankStatementAnalyzer (thin orchestrator, ~200 lines)
                            ← TransactionPatternTrainer (stays here — it's aggregation, not parsing)
        schemas.py          ← unchanged
```

---

## Approach — Extract, Don't Rewrite

The goal is to **move code**, not rewrite it. Extract each method verbatim. Only change import paths and `self.` references that become module-level functions.

**Extract order (do in this sequence — test after each step):**

### Step 1 — Extract `narration_enricher.py`

Move from `analyzer.py` to `enrichers/narration_enricher.py`:
- `analyze_narration_details(narration: str) -> dict` — convert from method to standalone function
- All the regex-supporting dicts (`upi_banks`, `merchants_and_categories`, `payment_methods_keywords`, etc.) — move them to module-level constants
- `CANONICAL_CATEGORIES` and `REGEX_TO_CANONICAL` already live in `services/categories.py` — import from there, don't duplicate

In `analyzer.py`, replace the method body with:
```python
from app.enrichers.narration_enricher import analyze_narration_details
# ... inside BankStatementAnalyzer:
details = analyze_narration_details(narration)
```

Run `pytest` after this step.

### Step 2 — Extract `confidence_scorer.py`

Move from `analyzer.py` to `scorers/confidence_scorer.py`:
- `calculate_confidence_score(txn: dict) -> float` — standalone function

In `analyzer.py`:
```python
from app.scorers.confidence_scorer import calculate_confidence_score
```

Run `pytest` after this step.

### Step 3 — Extract `pdf_parser.py`

Move from `analyzer.py` to `parsers/pdf_parser.py`:
- `_process_pdf_transactions(self, file_path: str) -> list[dict]`
  - Convert to a standalone function: `process_pdf_transactions(file_path: str, ...) -> list[dict]`
  - Import `analyze_narration_details` and `calculate_confidence_score` from the new modules
- `_looks_like_header(row) -> bool` — static method → standalone function

Run `pytest` after this step.

### Step 4 — Extract `excel_parser.py`

Move from `analyzer.py` to `parsers/excel_parser.py`:
- `_process_excel_csv(self, file_path: str) -> list[dict]`
- `detect_header_row(df) -> int`
- `find_column(df, keywords) -> Optional[str]`
- `parse_amount(value) -> Optional[float]`
- `normalize_date(value) -> str`
- `_deduplicate_transactions(transactions) -> list[dict]`

These are utility functions — convert from methods to standalone functions. Import them in `analyzer.py` for backward compatibility.

Run `pytest` after this step.

### Step 5 — Thin `analyzer.py`

After all extractions, `BankStatementAnalyzer` should be:
- `extract_transactions(file_path)` — orchestrates `process_excel_csv()` or `process_pdf_transactions()` based on extension
- `_extract_metadata_from_text(text)` — stays (it's specific to the metadata layer, not a standalone concern)
- Constructor and any remaining glue

`TransactionPatternTrainer` stays in `analyzer.py` — it's aggregation/stats, not parsing.

---

## What Must Not Change

- The import path `from app.models.analyzer import BankStatementAnalyzer, TransactionPatternTrainer` must still work. Do not move these classes.
- `from app.models.analyzer import AnalyzeModel` must still work (used in `analyze.py` router if present).
- All 38+ existing tests must pass with zero modifications to test files.
- The external JSON response shape is unchanged — this is a pure internal refactor.

---

## TD-008 — Shared Column Detection

As part of the Excel/PDF extraction, `find_column()` and the credit/debit/amount resolution logic are currently duplicated between `_process_excel_csv` and `_process_pdf_transactions`. Both should use the same `find_column()` from `excel_parser.py` after the split. The PDF path already uses similar logic — confirm it imports and calls the same function after the split, not its own copy.

---

## Verification

```bash
cd backend
pytest -v                   # all ~38+ tests green, zero modifications to test files
```

Also confirm:
```bash
wc -l backend/app/models/analyzer.py   # should be < 300 lines after split
```

In Swagger UI (`/docs`) — all existing endpoints still work. Upload a statement via the UI and confirm the response shape is identical to pre-split.

---

## Constraints

- **Do not rename public-facing classes** (`BankStatementAnalyzer`, `TransactionPatternTrainer`, `AnalyzeModel`) — only internal helpers move.
- **Extract verbatim, test after each step.** Do not refactor the logic while moving it. One concern per commit.
- **No new dependencies.** All new modules use only what's already in `requirements.txt`.
- If a step breaks tests, stop, debug, and fix before continuing to the next step.
