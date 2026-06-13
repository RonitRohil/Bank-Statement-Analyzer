# Prompt: Multi-page PDF Row Stitching — TD-021

**Task:** Fix the silent data loss bug where PDF table continuation rows on page 2+ are consumed as headers and dropped.  
**Sprint ref:** Sprint-02 · Tech debt: TD-021  
**Estimated time:** 3 hours  
**Severity:** 🟠 High — real data loss. Every PDF with a statement table spanning more than one page loses data silently.

---

## Why This Change Is Needed

`_process_pdf_transactions()` calls `pdfplumber` which returns a list of tables extracted per-page. For each extracted table, the code does:
```python
headers = table[0]   # assumes row 0 is always the header
rows = table[1:]
```

When a bank statement table continues onto page 2 without repeating its header row, `table[0]` on page 2 is the first data row (e.g. a transaction), not a header. That transaction is treated as column names and discarded. All subsequent rows of the continuation table are then skipped because the "detected columns" don't match.

Result: statements with 200 transactions across 4 pages might parse to only 50 transactions — the first page's worth. No error. No warning. Just missing data.

---

## Files to Read First

1. `backend-v2/app/models/analyzer.py` — search for `_process_pdf_transactions` and read the full method (it's around 150 lines)
2. `backend/app/models/analyzeModel.py` — the Flask version of the same method (they should be identical)
3. `docs/tech-debt.md` — TD-021 entry
4. `docs/code-review.md` — CR-C-01 entry

This fix must be applied to **both** `backend/app/models/analyzeModel.py` AND `backend-v2/app/models/analyzer.py` — they're copies and both need updating.

---

## The Fix: Carry the Last Good Header Forward

The approach: keep track of the last header row we successfully detected. When a new table's row 0 doesn't look like a header (i.e., it doesn't contain any of the expected column name keywords), assume this is a continuation and reuse the last header.

**How to detect if row 0 is a real header vs a data row:**
- Headers contain keywords like: `date`, `narration`, `description`, `debit`, `credit`, `amount`, `balance`, `particulars`, `withdrawal`, `deposit`
- Data rows contain: dates (`DD/MM/YYYY`, `YYYY-MM-DD`), amounts (`1,234.56`), or transaction codes

Use the existing `find_column()` function — if we can find at least one meaningful column in `table[0]`, it's a header. If `find_column()` returns `None` for all expected column names, assume it's a continuation page.

**Implementation:**

In `_process_pdf_transactions`, before the loop over `tables`, initialize:
```python
last_known_headers = None
last_known_col_map = None   # the column index map from the last good header
```

Inside the loop, where we currently do `headers = table[0]`, change to:

```python
def _looks_like_header(self, row):
    """Return True if this row looks like a column header, not a data row."""
    if not row:
        return False
    header_keywords = {
        "date", "narration", "description", "debit", "credit",
        "amount", "balance", "particulars", "withdrawal", "deposit",
        "txn", "transaction", "ref", "details", "chq"
    }
    row_text = " ".join(str(cell).lower() for cell in row if cell)
    return any(kw in row_text for kw in header_keywords)
```

Then in the table loop:
```python
for table in tables:
    if not table or len(table) < 2:
        continue
    
    if self._looks_like_header(table[0]):
        # This table starts with a real header — use it
        headers = table[0]
        rows = table[1:]
        last_known_headers = headers
        # (detect columns from this header as before)
    elif last_known_headers is not None:
        # Continuation page — no header row, reuse last known header
        logger.debug("[PDF] Continuation table detected — reusing header from previous page")
        headers = last_known_headers
        rows = table  # all rows are data rows
    else:
        # First table and doesn't look like a header — skip (can't process without column map)
        logger.warning("[PDF] First PDF table has no recognizable header — skipping")
        continue
    
    # (rest of the existing processing logic)
```

---

## Constraints

- Apply the fix to **both** `analyzeModel.py` (Flask) and `analyzer.py` (FastAPI) — identical change in both files
- Do not change the column detection logic itself (`find_column()`, `detect_header_row()`) — only change how headers are carried across tables
- The `_looks_like_header()` method should be a method on the class, not a standalone function
- If you find that `_looks_like_header` would be cleaner as a `@staticmethod`, that's fine — explain the choice
- Do not change the Excel/CSV processing path — this is PDF-only

---

## Verification Steps

You'll need a multi-page PDF. If you don't have one:
1. Create a mock by patching `pdfplumber.PDF.pages` to return two table sets — one with a header, one without
2. Or find a real bank statement PDF that has transactions on page 2+

Manual test:
1. Upload a multi-page PDF statement
2. Count transactions in the response — should be all transactions across all pages
3. Check logs for `[PDF] Continuation table detected` — should appear for each continuation page
4. Upload the same PDF to the Flask backend (port 5000) and compare counts — FastAPI should now return more (the correct number)

Unit test (add to `backend-v2/tests/test_analyze.py` or a new `test_pdf_parsing.py`):
```python
def test_looks_like_header_identifies_headers():
    analyzer = BankStatementAnalyzer("dummy.pdf")
    assert analyzer._looks_like_header(["Date", "Narration", "Debit", "Credit", "Balance"]) is True
    assert analyzer._looks_like_header(["01/01/2024", "UPI/123/Swiggy", "500.00", "", "24500.00"]) is False
    assert analyzer._looks_like_header(["", None, "", "", ""]) is False
```

---

## Commit Message (hand to Ronit)

```
fix(td-021): carry last known header across multi-page PDF tables

When a PDF statement table spans pages without repeating its header,
the continuation page's first data row was being consumed as column
names — silent data loss for every transaction on pages 2+.

Fix: _looks_like_header() detects whether table[0] is a real header.
If not, reuse last_known_headers from the previous table (continuation).

Applied to both backend/app/models/analyzeModel.py and
backend-v2/app/models/analyzer.py.

Logs "[PDF] Continuation table detected" at DEBUG for visibility.
```

---

## After This Task

Write `docs/study/multipage-pdf-fix-td021.md` covering:
- How pdfplumber returns tables (one list per page, not one merged table)
- Why the original code's assumption (`table[0]` = header always) fails
- The `_looks_like_header` heuristic: what it catches and what it might miss
- What to do if a bank uses an unusual header format

Update `docs/changelog.md` and `docs/tech-debt.md` (mark TD-021 ✅).
