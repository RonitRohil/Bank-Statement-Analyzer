# Code Review Report — Bank Statement Analyzer

**Date:** 2026-05-30
**Reviewed by:** Claude (Cowork)
**Scope:** Full codebase as it stands *after* the Sprint-01 fixes — backend (Python/Flask) + frontend (React/TypeScript)
**Verdict:** 🟠 **Request Changes** — one critical fix regressed/never landed; the rest are hardening items

> This supersedes the 2026-05-29 review. The earlier review described the pre-fix codebase. Most Priority-1 items were genuinely fixed in code. **One was not** (see CR-01), which is the most important finding here.

---

## What got fixed since the last review ✅

Verified by reading the current source, not the sprint notes:

| Previous issue | Status | Evidence |
|----------------|--------|----------|
| `debug=True` hardcoded | ✅ Fixed | `run.py` now reads `FLASK_DEBUG` env, defaults `false` |
| Uploaded files never deleted | ✅ Fixed | `analyzeController.py` deletes in a `finally` block |
| No file size/extension validation | ✅ Fixed | Controller checks `ALLOWED_EXTENSIONS` + `MAX_UPLOAD_SIZE` |
| Filename collisions / path traversal | ✅ Fixed | `secure_filename` + `uuid4` prefix |
| `Config.INTEGRATION_URL/AUTH` undefined | ✅ Fixed | Now defined in `Config` with env defaults |
| CORS wildcard default | ✅ Fixed | Defaults to `http://localhost:3000` |
| 4 dead classes + `sklearn` imports | ✅ Fixed | Removed; replaced with a tracking comment |
| `confidence_score` missing on PDF path | ✅ Fixed | Scoring loop now present in `_process_pdf_transactions` |
| `required_cols_pdf` `and`→`or` bug | ✅ Fixed | PDF path now uses `or`, matching Excel path |
| Double-assignment typo | ✅ Fixed | Single assignment now |
| `print()` instead of `logging` | ✅ Fixed | `logger.*` throughout |
| Frontend hardcoded API URL | ✅ Fixed | `api.ts` reads `VITE_API_URL` |

Solid execution. The model file is down to ~1,280 readable lines and the controller is now genuinely clean.

---

## Critical Issues

| # | File | Location | Issue | Severity |
|---|------|----------|-------|----------|
| CR-01 | `backend/requirements.txt` | whole file | **Still UTF-16 encoded.** The "fix" never landed. `hexdump` shows a null byte after every character (`46 00 6c 00 ...`). `pip install -r requirements.txt` fails on any clean environment. | 🔴 Critical |

### CR-01 — `requirements.txt` is still UTF-16 (regression / un-landed fix)

The 2026-05-29 sprint log lists this as "Fixed UTF-16 encoding → clean UTF-8". The file on disk is **still UTF-16-LE**:

```
00000000  46 00 6c 00 61 00 73 00  6b 00 3d 00 3d 00 33 00  |F.l.a.s.k.=.=.3.|
```

Every other byte is `0x00`. A fresh `pip install -r requirements.txt` will throw an encoding error or read garbage. This blocks every new contributor and every CI/Docker build before anything else runs.

**Why it probably happened:** the file was re-saved from a PowerShell redirect (`>` in PowerShell writes UTF-16 by default) or an editor that preserved the original encoding. Sprint notes were written assuming the edit took.

**Fix — force UTF-8, no BOM:**
```bash
# from repo root, in a normal shell (not PowerShell >)
printf '%s\n' \
  "Flask==3.1.2" "flask-cors==6.0.1" "python-dotenv==1.2.1" \
  "pdfplumber==0.11.8" "pandas==2.3.3" "openpyxl==3.1.5" "requests==2.32.5" \
  > backend/requirements.txt
file backend/requirements.txt   # should say: ASCII text
```
**Add a guard so this can't silently regress:** a one-line CI check — `file backend/requirements.txt | grep -q ASCII` — or a pre-commit hook.

---

## Security Issues

### CR-S-01 🟠 — No authentication on the analyze endpoint
**File:** `backend/app/routes/routes.py`

`POST /api/analyze/bank/statement` is fully public. Anyone who can reach the port can upload statements and consume CPU (pdfplumber parsing is expensive). Acceptable for a localhost tool; a real exposure the moment this is deployed anywhere networked.

**Fix (minimal):** static API-key check via a `before_request` hook or decorator. Anything beyond a personal tool → real auth (session/JWT) and per-IP rate limiting (`flask-limiter`).

### CR-S-02 🟠 — Dead `verify_bank_account_with_pennyless` still ships hardcoded identity data
**File:** `backend/app/models/analyzeModel.py` (~lines 1097–1172)

The function is never called, but it's still in the tree with:
```python
name = "stco"
mobile = "9999999999"
```
Dead code that would POST a hardcoded name/mobile to an external API if ever wired up. With `INTEGRATION_URL` now defaulting to `""`, the request URL becomes malformed rather than raising — so it fails quietly instead of loudly.

**Fix:** delete the function until the integration is real. If you want to keep it, move it behind a feature flag and pull `name`/`mobile` from the request, never hardcode.

### CR-S-03 🟡 — Extension whitelist trusts the filename, not the bytes
**File:** `backend/app/controllers/analyzeController.py`

Validation keys off the file *extension*. A file named `x.pdf` that is actually something else passes the gate. pdfplumber/pandas will fail safely on garbage, so the blast radius is small, but for defense in depth verify magic bytes (e.g. `%PDF`, `PK\x03\x04` for xlsx) before parsing.

### CR-S-04 🟡 — No bound on PDF page count / parsing time
A 20 MB PDF can still contain thousands of pages or a decompression bomb. The size cap helps; a page-count cap and a parse timeout (run parsing in a worker with a wall-clock limit) would close the DoS vector. This pairs naturally with the planned async/job-queue work.

---

## Correctness Issues

### CR-C-01 🟠 — Multi-page PDF tables lose their continuation rows
**File:** `backend/app/models/analyzeModel.py`, `_process_pdf_transactions`

Each page's tables are extracted independently and `table[0]` is always treated as the header:
```python
df = pd.DataFrame(table[1:], columns=table[0])
```
When a transaction table spills onto the next page **without repeating its header** (very common in real statements), page 2's first *data* row is consumed as column headers, then the table fails the `required_cols` check and is skipped — silently dropping a page of transactions. The user sees a lower total with no error.

**Fix options:** (a) carry the last good header forward when a table's first row looks like data, or (b) switch to coordinate/word-based extraction and stitch rows across pages, or (c) detect "headerless continuation" by column-count match against the previous table.

### CR-C-02 🟡 — `transaction_reference` regex can capture account/phone numbers
**File:** `analyze_narration_details`, fallback ref patterns (~line 908)

The final fallback `r"\b(?:\d{10,})\b"` grabs *any* 10+ digit run. In an IMPS/NEFT narration that also contains a beneficiary account number or a 10-digit mobile, the wrong number can land in `transaction_reference`. Low-severity data-quality noise, but it feeds confidence scoring and merchant insights.

**Fix:** require a labeled prefix (RRN/UTR/REF/TXN) for the numeric fallback, or rank candidates and prefer 12/16-digit UTR-shaped strings.

### CR-C-03 🟡 — `account_holder` regex is greedy and order-dependent
**File:** `_extract_metadata_from_text` (~line 755)

`([A-Z][A-Z\s\.&,']+)` is broad — on statements where the header block is mostly uppercase (bank name, address, column titles), it can capture the wrong span as the account holder. There's no validation that the captured string looks like a name (length bounds, word count, not a known bank/keyword).

**Fix:** add sanity filters (2–4 words, not in the bank-keyword list, < 40 chars) or fall back to `None` rather than a confident-but-wrong value. This is exactly the kind of brittle extraction the planned NER/LLM work should replace.

### CR-C-04 🟡 — Confidence score penalizes balance-less statements systematically
**File:** `calculate_confidence_score`

`-0.05` for missing `balance` is fine in isolation, but many valid statement formats (especially credit-card and some CSV exports) simply don't carry a running balance. Every transaction from those files takes a flat hit, dragging `overall_score` down and tripping the `high_confidence_txns` threshold for reasons unrelated to extraction quality.

**Fix:** make the balance penalty conditional on whether *any* transaction in the file had a balance (i.e., the format is expected to have one), not per-transaction unconditionally.

### CR-C-05 🟡 — No transaction de-duplication
If the same table is extracted twice (overlapping pdfplumber table regions, or a repeated summary block), duplicate transactions enter the list and skew `merchant_insights` and totals. There's no dedupe on `(date, amount, narration, balance)`.

**Fix:** dedupe on a composite key before scoring.

---

## Maintainability Issues

### CR-M-01 🟡 — No health endpoint
**File:** `backend/app/routes/routes.py`

Still no `GET /api/health`. Required for any container/orchestrator/uptime check and it's a 3-line add. (The FastAPI ADR lists it as an action item — worth doing in the current Flask app too so monitoring isn't blocked on the migration.)

### CR-M-02 🟡 — Column-detection block is duplicated across Excel and PDF paths
The identical `find_column([...])` sequence for date/credit/debit/amount/narration/balance/account appears in both `_process_excel_csv` and `_process_pdf_transactions`, as does the credit/debit/amount → `(amount, txn_type)` resolution. Two copies that must change together.

**Fix:** extract `_detect_columns(df) -> ColumnMap` and `_resolve_amount(row, cols) -> (amount, type)`. Cuts ~80 lines and removes a drift risk.

### CR-M-03 🟡 — `BankStatementAnalyzer` is still a single ~1,280-line class
Routing, Excel parsing, PDF parsing, date normalization, narration enrichment, metadata extraction, and scoring all live in one class. It works, but it's hard to unit-test in isolation. The FastAPI migration is the natural moment to split into `parsers/`, `enrichers/`, `scorers/` (see tech-debt TD-007).

### CR-M-04 🟡 — Zero automated tests
No pytest, no Vitest. Every one of the correctness items above is the kind of thing a 20-line unit test would catch and lock down. This is the highest-leverage maintainability investment — and a prerequisite for safely doing the FastAPI port and the ML work.

### CR-M-05 🟢 — `.gitIgnore` is still capitalized
The file is `.gitIgnore` (capital I). On case-sensitive filesystems (Linux CI, most Docker builds) git does not recognize it, so `__pycache__`/`.pyc` and `venv/` may get tracked. Rename to `.gitignore` and confirm it ignores `**/__pycache__/`, `*.pyc`, `venv/`, `.env`.

---

## Frontend notes

- **`TransactionTable` renders every row** (`safeTransactions.map(...)`) with no pagination or virtualization. Fine for a 60-row statement; janky at 1,000+. Add simple pagination or `@tanstack/react-virtual` before the multi-statement/history features land. (tech-debt TD-018, still open.)
- **Row key** `` `${txn.transaction_reference}-${index}` `` is fine, but `transaction_reference` is frequently `null` — keys collapse to `null-0`, `null-1`. Harmless because `index` disambiguates, but worth a cleaner stable key once dedupe exists.
- **`types.ts` is well-maintained** and matches the backend response shape. When you move to FastAPI + Pydantic, generate these types from the OpenAPI schema (`openapi-typescript`) so they can't drift.
- **`api.ts` error handling is genuinely good** — distinguishes network vs HTTP vs non-JSON error bodies. Nice.

---

## What Looks Good ✅

- The Sprint-01 cleanup was real and well-scoped — the controller and config are now clean and production-shaped.
- `analyze_narration_details` covers the major Indian rails (UPI structured, VSI card, IMPS, NEFT/RTGS, BBPS) and clearly comes from real data.
- Penalty-based `calculate_confidence_score` is transparent and debuggable — the right call for v1 over a black-box model.
- `detect_header_row` handling of headers partway down a file is a real-world-aware touch.
- Per-section `ErrorBoundary` on the dashboard is a solid production pattern.
- Logging migration (`print` → `logger`) means the app is now actually observable.

---

## Suggested Fix Order

1. **CR-01** — re-encode `requirements.txt` to UTF-8 + add a CI guard. Nothing else (Docker, CI, onboarding) works until this is real.
2. **CR-M-05** — rename `.gitIgnore` → `.gitignore` (one command, prevents secret/`.env` leakage).
3. **CR-C-01** — multi-page PDF continuation rows (data-loss bug; matters for the PDF-compatibility goal).
4. **CR-M-01** — add `GET /api/health`.
5. **CR-S-02** — delete the dead Pennyless function with its hardcoded identity data.
6. **CR-M-04** — stand up pytest with unit tests for `parse_amount`, `normalize_date`, `find_column`, `analyze_narration_details` *before* the FastAPI port.
7. **CR-C-02..05** — narration/metadata/dedupe quality fixes (bundle into one "extraction hardening" patch).
8. **CR-M-02/03** — refactor shared column detection + split the module (do it as part of the FastAPI migration).

---

*Prioritized backlog with IDs in `tech-debt.md`. Forward-looking feature analysis in `improvement-analysis.md`. Framework decision in `adr-001-flask-vs-fastapi.md`.*
