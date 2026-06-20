# Study: Multi-page PDF Row Stitching Fix (TD-021)

**Sprint:** Sprint-02  
**Date:** 2026-06-19  
**Files changed:** `backend-v2/app/models/analyzer.py`, `backend/app/models/analyzeModel.py`

---

## What was built

`_looks_like_header(row)` — a staticmethod on `BankStatementAnalyzer` that inspects a single table row and returns `True` if it looks like a column header. Used in `_process_pdf_transactions` to decide whether `table[0]` is a real header or a data row that belongs on a continuation page.

---

## Why it was built

Silent data loss. A PDF bank statement spanning 4 pages with 200 transactions might parse to 50 — the first page's worth — with no error, no warning, no indication anything was wrong.

---

## How pdfplumber returns tables

`pdfplumber` extracts tables **per page**. `pdf.pages[0].extract_tables()` returns a list of tables found on page 0 only. There is no merged, multi-page table — you get one table list per page, and you iterate over all pages yourself.

Each extracted table is a `list[list[str | None]]` — a list of rows, where each row is a list of cell values. Row 0 is whatever the first row of that table is on that particular page.

```python
# What pdfplumber gives you for a 3-page statement:
page 1: [["Date", "Narration", "Debit", "Credit", "Balance"],
         ["01/01/2024", "UPI/ZOMATO", "500", "", "24500"]]

page 2: [["01/01/2024", "SALARY CREDIT", "", "50000", "74500"],   # no header
         ["02/01/2024", "NEFT/HDFC/...", "2000", "", "72500"]]

page 3: [["03/01/2024", "ATM WITHDRAWAL", "3000", "", "69500"]]   # no header
```

---

## Why the original code's assumption failed

The original loop did:

```python
df = pd.DataFrame(table[1:], columns=table[0])
```

This **always** assumed `table[0]` is the header row. On page 2, `table[0]` is `["01/01/2024", "SALARY CREDIT", "", "50000", "74500"]` — a real transaction. That row became the column names (`"01/01/2024"`, `"SALARY CREDIT"`, etc.) and was discarded. The remaining rows were then processed with nonsense column names, and `find_column()` returned `None` for date, narration, and amount — so the entire table was skipped.

Result: every continuation page loses all its transactions. A 4-page statement returns ~25% of its data.

---

## The `_looks_like_header` heuristic

```python
@staticmethod
def _looks_like_header(row):
    if not row:
        return False
    header_keywords = {
        "date", "narration", "description", "debit", "credit",
        "amount", "balance", "particulars", "withdrawal", "deposit",
        "txn", "transaction", "ref", "details", "chq",
    }
    row_text = " ".join(str(cell).lower() for cell in row if cell)
    return any(kw in row_text for kw in header_keywords)
```

**What it catches:**
- Standard SBI/HDFC/ICICI/Kotak headers: `Date`, `Narration`, `Debit`, `Credit`, `Balance`
- Variants: `Txn Date`, `Particulars`, `Withdrawal`, `Deposit`, `Chq No`
- Abbreviated: `Txn`, `Ref`, `Details`

**What it might miss:**
- Banks that use non-English headers (some cooperative banks use Hindi/regional transliterations)
- Heavily abbreviated headers like `Dt`, `Amt`, `Narr` that don't contain the full keyword
- Headers in ALL-CAPS with no recognizable substring (very unlikely for standard banks)

**What it won't false-positive on:**
- Date strings (`01/01/2024`) — contain no header keyword
- Amount strings (`50,000.00`) — contain no header keyword
- Numeric transaction IDs — no keyword match

The heuristic is intentionally loose (substring match, not exact) because banks format column names inconsistently. A false positive (treating a data row as a header) is recoverable — `find_column()` would return `None` for most columns and the table would be skipped with a warning. A false negative (treating a header as data) would cause missing columns but the continuation logic would kick in and reuse the last valid header — arguably better behavior than the original silent drop.

---

## What to do if a bank uses an unusual header format

If a bank's header row isn't caught by `_looks_like_header`:

1. **Add the keyword.** The `header_keywords` set in `_looks_like_header` is the right place to extend. Keep keywords short (substring match means `"txn"` catches `"txn date"`, `"txn no"`, etc.).

2. **Check the raw PDF.** Use `pdfplumber.open(file).pages[0].extract_tables()` in a Python REPL to see what pdfplumber actually extracts from that bank's header row. Sometimes cells are merged or split differently than the visual appearance.

3. **Last resort — coordinate stitching.** If the bank never repeats headers across pages and uses non-standard column names, the fix needs to be extended to stitch tables across pages by matching column positions (x-coordinates) rather than keyword detection. This is more complex and would be a separate TD item.

---

## Key code paths after the fix

```
_process_pdf_transactions()
  └── last_known_headers = None
  └── for page in pdf.pages:
        for table in page.extract_tables():
          if _looks_like_header(table[0]):       # standard page
            headers = table[0]
            rows = table[1:]
            last_known_headers = headers          # remember for continuation
          elif last_known_headers is not None:   # continuation page
            headers = last_known_headers
            rows = table                         # ALL rows are data
          else:                                  # first table, unrecognized
            skip (warning logged)
          df = pd.DataFrame(rows, columns=headers)
          tables_df_list.append(df)
```

---

## What's next

- Manual test with a real multi-page bank PDF — upload and count transactions per page vs. total
- TD-024: transaction deduplication — continuation pages may now produce duplicate rows if a bank repeats the last row of a page as the first row of the next page (carry-over pattern)
