# Study: Sprint 01 — Full Audit, Critical Fixes, and Planning

**Date:** 2026-05-29  
**Sprint:** Sprint 01  
**Author:** Claude (Cowork)

---

## 1. What Was Built / Done

This sprint was entirely a **code quality + planning sprint** — no new user-facing features. The work done:

1. Full codebase audit (all backend + frontend files read)
2. Created docs/ folder with 7 documents
3. Applied 11 critical/high-priority bug fixes
4. Made two major architecture decisions (FastAPI migration, ML/AI roadmap)
5. Established the development process and workflow

---

## 2. Critical Fixes — What They Were and Why

### Fix 1: requirements.txt was UTF-16 encoded
The `requirements.txt` file had null bytes between every character — a sign it was saved in UTF-16 instead of UTF-8. On Linux (and most CI environments), `pip install -r requirements.txt` would produce `Invalid requirement` errors for every line. The file was regenerated as clean UTF-8 with only direct dependencies listed (not a full `pip freeze`).

**Key insight:** A `pip freeze` output includes everything in your venv — transitive dependencies, build tools, virtualenv itself. That's not what `requirements.txt` should be. Only list the packages you directly `import`.

---

### Fix 2: Config.INTEGRATION_URL/AUTH were missing
`analyzeModel.py` had a method `verify_bank_account_with_pennyless()` that used `Config.INTEGRATION_URL` and `Config.INTEGRATION_AUTH`. These were never defined in the `Config` class. The fix added them as empty-string defaults loaded from env vars.

**Key insight:** In Flask/Python, a missing class attribute doesn't raise an error until you try to access it. This is why the app could start fine but would blow up with `AttributeError` only when that specific code path ran. Always validate your config at startup.

---

### Fix 3: debug=True was hardcoded
`run.py` had `app.run(port=5000, debug=True)`. The Werkzeug debug mode does two dangerous things: it exposes an interactive Python console on any unhandled exception (an attacker can execute arbitrary code), and it auto-reloads the server on file changes. Neither is acceptable outside local dev.

**Fix pattern:**
```python
debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
app.run(port=5000, debug=debug)
```
This is the correct pattern — default to safe, opt in to debug explicitly.

---

### Fix 4: Uploaded files were never deleted
Every uploaded bank statement was saved to `uploads/` and never removed. Two problems: disk fills up over time, and sensitive financial data sits on the server's disk indefinitely.

The fix uses Python's `try/finally` pattern:
```python
try:
    result, status_code = analyzer.bank_statement_analysis(data)
    return result, status_code
finally:
    if os.path.exists(file_path):
        os.remove(file_path)
```
The `finally` block runs regardless of whether the analysis succeeds or raises an exception.

**Why `os.path.exists()` first?** If saving the file failed partway through (e.g., disk full), the file might not exist. `os.remove()` on a non-existent path raises `FileNotFoundError`.

---

### Fix 5: No file validation
The controller only checked `if uploaded_file.filename == ""`. This meant:
- A 10 GB file would be accepted and saved
- A `.exe` disguised as a `.pdf` would be accepted
- Multiple requests could race on the same filename

Three defenses added:
1. **Extension whitelist:** Only `.pdf`, `.csv`, `.xlsx`, `.xls`
2. **Size check:** Read file position to get size without loading into memory
3. **UUID prefix:** `{uuid4().hex}_{secure_filename}` prevents collisions and guessability

**How the size check works:**
```python
uploaded_file.seek(0, 2)   # Seek to end of file
file_size = uploaded_file.tell()  # Position = file size
uploaded_file.seek(0)      # Rewind for actual reading
```

---

### Fix 6: confidence_score missing from PDF path
The Excel parsing path had this loop after building transactions:
```python
for txn in transactions:
    txn["confidence_score"] = self.calculate_confidence_score(txn)
```
The PDF parsing path didn't. PDF transactions came back without `confidence_score`. The TypeScript interface declared it as required, so the frontend would get `undefined` and potentially crash.

The fix added the identical loop to the PDF path, plus the full `confidence_summary` dict to match the Excel response shape.

---

### Fix 7: `and` vs `or` in PDF column validation
```python
# Buggy (PDF path):
if not all(required_cols_pdf) and not (credit_col or debit_col or amount_col):

# Correct (Excel path):
if not all(required_cols) or not (credit_col or debit_col or amount_col):
```
With `and`, the guard only skips a table if **both** conditions are true simultaneously. With `or`, it skips a table if **either** condition is true — which is the intent. The `and` version would process tables missing date/narration columns as long as they had an amount column, leading to garbage output.

---

### Fix 8: Four dead classes removed
`EnhancedNarrationAnalyzer`, `TransactionPatternLearner`, `BalanceValidator`, `EnhancedConfidenceScorer` — all defined, none ever called. Combined: ~200 lines of misleading code.

`EnhancedNarrationAnalyzer.analyze()` referenced `self.nlp` which was never initialized — it would crash instantly if called. `TransactionPatternLearner` called `.day` on a date string (strings don't have `.day`).

Dead code is worse than no code because it implies intent that doesn't exist and misleads developers who read it.

---

### Fix 9: print() → logging module
All `print("message %s", value)` calls were wrong in two ways:
1. `print()` doesn't support `%s` format strings — it prints them literally as `"message %s" value` separated by a space
2. `print()` can't be filtered by log level or sent to a log aggregator

The `logging` module fixes both. `logger.debug("message %s", value)` formats correctly and is filterable.

---

### Fix 10: Hardcoded API URL in frontend
`api.ts` had `const API_URL = 'http://localhost:5000/...'`. This works locally but makes it impossible to deploy the frontend against a staging or production backend without modifying source code.

```typescript
// Before:
const API_URL = 'http://localhost:5000/api/analyze/bank/statement';

// After:
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:5000';
const API_URL = `${API_BASE}/api/analyze/bank/statement`;
```
`import.meta.env.VITE_API_URL` reads from the `.env.local` file at build time.

---

## 3. Architecture Decisions Made

### Decision 1: Migrate to FastAPI
**Context:** Flask is synchronous. LLM features require SSE streaming. Pydantic would eliminate manual validation code.  
**Decision:** Migrate to FastAPI. Keep Flask running in parallel during migration.  
**Full reasoning:** `docs/adr-001-flask-vs-fastapi.md`

### Decision 2: ML/AI hybrid approach
**Context:** Current regex-based categorization misses unknown merchants.  
**Decision:** LLM (Claude Haiku) as quick-win fallback for null categories; ML classifier (TF-IDF → sentence-transformers) for trained categorization; NER for receiver extraction.  
**Full reasoning:** `docs/ml-ai-brainstorm.md`

---

## 4. Key Concepts to Understand

### How `BankStatementAnalyzer` works (the core flow)
```
__init__(file_path)
  └→ extract_transactions()
       ├→ if .csv/.xlsx/.xls: _process_excel_csv()
       └→ if .pdf: _process_pdf_transactions()

Both paths do:
  1. Read file into DataFrame (pandas)
  2. detect_header_row() → find which row has column names
  3. find_column() → fuzzy match column names (date, credit, debit, balance, narration)
  4. For each row:
     - parse_amount() → clean currency symbols, handle Cr/Dr
     - normalize_date() → multiple format → ISO YYYY-MM-DD
     - analyze_narration_details() → regex extract UPI/IMPS/merchant/category
  5. calculate_confidence_score() → penalty-based quality score
  6. TransactionPatternTrainer.analyze() → merchant aggregation
  7. _extract_metadata_from_text/df() → account holder, IFSC, bank name
```

### Why confidence scoring is penalty-based (not absolute)
Starting at 1.0 and subtracting penalties is more intuitive than building up from 0. Each penalty has a clear meaning: "we lost 25% confidence because the date is missing." The final score is clamped to [0, 1].

### Why narration analysis is regex-based (not ML) today
Indian banking narrations have highly structured formats that regex handles well: `UPI/{id}/{remark}/{bank}/{txn_id}` is a fixed template. Regex is fast (~microseconds per narration), deterministic, and debuggable. ML adds latency and requires training data. The hybrid approach (regex primary, LLM fallback) gets 90% of the value with 10% of the complexity.

---

## 5. Gotchas and Edge Cases

- **PDF date parsing uses a different path than Excel.** Excel uses `normalize_date()`; the original PDF path used `pd.to_datetime()` directly. They've now been unified — always use `normalize_date()`.
- **`detect_header_row()` reads up to the first 20 rows.** Some bank statements have 10–15 rows of header metadata before the transaction table starts.
- **`find_column()` is case-insensitive partial match.** This means a column named `"Transaction Narration"` will match the keyword `"narration"`. Good for flexibility, but be aware it's fuzzy.
- **Amount parsing rejects date-like patterns first.** `parse_amount("2025-02-05")` returns None because the regex `\d{4}[-/]\d{2}[-/]\d{2}` catches it. This prevents dates accidentally parsed as amounts (which happen in some bank statement formats).
- **Uploaded files are now saved with UUID prefix.** If you're debugging and looking for a file in `uploads/`, it will be named `{uuid}_{original_name}` — but it's also deleted immediately after analysis, so you'd need to add a breakpoint to catch it.

---

## 6. What's Next (Sprint 02)

- [ ] FastAPI scaffold — `backend-v2/` with health endpoint and Pydantic models (BSA-02)
- [ ] Port `/api/analyze/bank/statement` to FastAPI (BSA-03)
- [ ] LLM categorization fallback using Claude Haiku (BSA-04)
- [ ] Automated financial summary endpoint (BSA-05)
- [ ] FinanceAssistant Phase 2 top priority feature
