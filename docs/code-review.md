# Code Review Report — Bank Statement Analyzer

**Date:** 2026-05-29  
**Reviewed by:** Claude (Cowork)  
**Scope:** Full codebase — backend (Python/Flask) + frontend (React/TypeScript)  
**Verdict:** 🔴 **Request Changes** — several critical issues must be fixed before production use

---

## Critical Issues

| # | File | Location | Issue | Severity |
|---|------|----------|-------|----------|
| 1 | `backend/requirements.txt` | entire file | UTF-16 encoded — `pip install -r requirements.txt` will fail on any standard environment | 🔴 Critical |
| 2 | `backend/app/config/config.py` | `Config` class | `Config.INTEGRATION_URL` and `Config.INTEGRATION_AUTH` referenced in `analyzeModel.py` but never defined — raises `AttributeError` at runtime | 🔴 Critical |
| 3 | `backend/run.py` | line 4 | `debug=True` hard-coded — exposes Werkzeug interactive debugger in any environment | 🔴 Critical |
| 4 | `backend/app/controllers/analyzeController.py` | `analyze_statement()` | Files saved to `uploads/` and never deleted — sensitive financial data accumulates on disk indefinitely | 🔴 Critical |
| 5 | `backend/app/models/analyzeModel.py` | `EnhancedNarrationAnalyzer.analyze()` | References `self.nlp` which is never set — raises `AttributeError` if ever called | 🔴 Critical |

---

## Security Issues

### S-01 — No file type or size validation
**File:** `backend/app/controllers/analyzeController.py`

```python
# Current — only checks if filename is empty
if uploaded_file.filename == "":
    return jsonify({"success": False, "message": "Invalid file."}), 400
```

No check on: file extension whitelist, MIME type, or file size. An attacker can upload a 500 MB archive, a malicious script, or a crafted PDF designed to exploit pdfplumber.

**Fix:**
```python
ALLOWED_EXTENSIONS = {'.pdf', '.csv', '.xlsx', '.xls'}
MAX_SIZE = 20 * 1024 * 1024  # 20 MB

ext = os.path.splitext(secure_filename(uploaded_file.filename))[1].lower()
if ext not in ALLOWED_EXTENSIONS:
    return jsonify({"success": False, "message": "File type not allowed."}), 400

uploaded_file.seek(0, 2)
if uploaded_file.tell() > MAX_SIZE:
    return jsonify({"success": False, "message": "File exceeds 20 MB limit."}), 400
uploaded_file.seek(0)
```

---

### S-02 — CORS wildcard default
**File:** `backend/app/config/config.py`

```python
CORS_URLS = os.getenv("CORS_URLS", "*")
```

If `CORS_URLS` is not set, every origin (including `evil.com`) can call this API with credentials. For a local dev tool this is inconvenient but tolerable; for any networked deployment it is a real exposure.

**Fix:** Default to `http://localhost:3000` or raise a startup warning if the variable is unset.

---

### S-03 — No API authentication
**File:** `backend/app/routes/routes.py`

The single endpoint has no auth middleware. Any client that can reach port 5000 can submit files. The `Config` class has no `SECRET_KEY` defined.

**Fix (minimal):** Add a static API key check via a decorator or middleware. For anything beyond a local tool, add proper auth.

---

### S-04 — Hardcoded dummy credentials in `verify_bank_account_with_pennyless`
**File:** `backend/app/models/analyzeModel.py`

```python
name = "stco"
mobile = "9999999999"
```

These placeholder values are hardcoded and would be sent to a real external verification API. Even if the integration is incomplete, this is a bad pattern — values like this end up in logs and API provider audit trails.

---

## Correctness Issues

### C-01 — `confidence_score` missing from PDF path
**File:** `backend/app/models/analyzeModel.py`

In `_process_excel_csv`, after building the transaction list:
```python
for txn in transactions:
    txn["confidence_score"] = self.calculate_confidence_score(txn)
```

This loop is **absent** from `_process_pdf_transactions`. PDF transactions are returned without a `confidence_score` field. The frontend `types.ts` declares `confidence_score: number` as required on `Transaction`, which will cause rendering bugs.

**Fix:** Add the same loop before the return statement in `_process_pdf_transactions`, or extract it into a shared helper.

---

### C-02 — Double assignment typo
**File:** `backend/app/models/analyzeModel.py`, `_process_excel_csv`

```python
parsed_date = parsed_date = self.normalize_date(transaction_date_str, index)
```

The variable is assigned twice in the same statement — a copy-paste artifact. Functionally harmless but signals carelessness.

**Fix:** `parsed_date = self.normalize_date(transaction_date_str, index)`

---

### C-03 — Silent swallowing of row-level errors
**File:** `backend/app/models/analyzeModel.py`, `_process_excel_csv`

```python
except Exception as inner_err:
    print("Skipping row %s due to parsing error", index)
```

The actual exception `inner_err` is never logged — only the row index. If there is a systematic bug (e.g., a column name mismatch), every row silently fails and the user gets an empty transaction list with no useful feedback.

**Fix:**
```python
except Exception as inner_err:
    logger.warning("Skipping row %s due to parsing error: %s", index, inner_err, exc_info=True)
```

---

### C-04 — `print()` used with `%s` format but no `%` operator
**File:** `backend/app/models/analyzeModel.py` (throughout)

```python
print("Detected header row at index: %s", i)
print("Excel/CSV Normalized Columns: %s", df.columns.tolist())
```

`print()` doesn't accept `%s` format strings — it just prints the format string and the argument as separate items separated by a space. These log lines produce garbled output like `"Detected header row at index: %s 3"` instead of `"Detected header row at index: 3"`.

This works as-is (the output is just ugly), but it means all these "logs" are misleading. They'll work correctly once migrated to `logging.debug("...", i)`.

---

### C-05 — `required_cols_pdf` logic is inverted
**File:** `backend/app/models/analyzeModel.py`, `_process_pdf_transactions`

```python
required_cols_pdf = [date_col, narration_col]
if not all(required_cols_pdf) and not (credit_col or debit_col or amount_col):
    continue
```

This says: "skip if both (date or narration missing) AND (no amount columns)". The `and` should likely be `or` — a table should be skipped if it's missing either its date/narration columns OR its amount columns, not only when both conditions are simultaneously true.

Compare with the Excel path which uses a stricter check:
```python
if not all(required_cols) or not (credit_col or debit_col or amount_col):
```

The PDF path uses `and` — the Excel path uses `or`. One of these is wrong. The `or` (Excel) is more defensive.

**Fix:** Change `and` to `or` in the PDF path to match the Excel path.

---

## Maintainability Issues

### M-01 — Four dead classes in `analyzeModel.py`
**File:** `backend/app/models/analyzeModel.py`

`EnhancedNarrationAnalyzer`, `TransactionPatternLearner`, `BalanceValidator`, and `EnhancedConfidenceScorer` are defined but never instantiated or called anywhere. They represent 200+ lines of aspirational code that inflates the file and misleads anyone reading it.

`EnhancedNarrationAnalyzer` contains a critical bug (`self.nlp` undefined). `TransactionPatternLearner.learn_patterns` calls `txn["transaction_date"].day` which would raise `AttributeError` since dates are stored as strings.

**Fix:** Remove all four. If the features are planned, open issues/tickets for them instead.

---

### M-02 — `sklearn` imported but not used
**File:** `backend/app/models/analyzeModel.py`

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.ensemble import RandomForestClassifier
```

None of these are used in any active code path. `scikit-learn` and `scipy` together add ~120 MB to the install. Remove until the ML categorization feature is actually implemented.

---

### M-03 — Dead variables
**File:** `backend/app/models/analyzeModel.py`, `_process_excel_csv`

```python
verification_tasks = []
txn_peer_map = []
```

Both initialized, nothing ever appended. Remove.

---

### M-04 — API base URL hardcoded in frontend
**File:** `frontend/services/api.ts`

```typescript
const API_URL = 'http://localhost:5000/api/analyze/bank/statement';
```

Cannot be overridden without editing source. Use `import.meta.env.VITE_API_URL`.

---

### M-05 — No health check endpoint
**File:** `backend/app/routes/routes.py`

There is no `GET /health` or `GET /api/health` endpoint. Impossible to use a load balancer, container orchestrator, or uptime monitor without one.

**Fix (2 lines):**
```python
@analyze_statement_bp.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200
```

---

## What Looks Good ✅

- **`secure_filename()`** is used when saving uploaded files — prevents path traversal attacks
- **`ErrorBoundary` per dashboard section** — a React crash in one chart doesn't kill the whole page
- **TypeScript types** in `types.ts` are comprehensive and match the API response shape well
- **`narration_details` regex patterns** cover the major Indian payment formats (UPI structured, IMPS, NEFT, RTGS, BBPS) — clearly built from real-world data
- **`calculate_confidence_score`** uses penalty-based scoring — a good, transparent approach over a black-box model for a v1
- **`detect_header_row`** gracefully handles bank statements that have header rows partway down the file — a common real-world challenge
- **Separate `ErrorBoundary` component** is a solid production pattern
- **`vite.config.ts`** correctly exposes `GEMINI_API_KEY` to the frontend via `define` (prepared for future AI features)
- **MVC structure** is clear and consistent — controller doesn't do business logic, model doesn't touch HTTP

---

## Suggested Fix Order

1. Fix `requirements.txt` encoding (TD-001) — nothing else works until this is done
2. Delete uploaded files after processing (TD-005)
3. Add `INTEGRATION_URL/AUTH` to Config, add `.env.example` (TD-002, TD-003)
4. Remove `debug=True` from run.py (TD-004)
5. Add file validation (size + extension whitelist) (S-01)
6. Fix `confidence_score` missing from PDF path (C-01)
7. Fix `required_cols_pdf` `and`→`or` (C-05)
8. Remove four dead classes (M-01) and sklearn imports (M-02)
9. Replace `print()` with `logging` (TD-012)
10. Add env var for API URL on frontend (M-04)

---

*Full prioritized backlog is in `tech-debt.md`. Architectural recommendations in `system-design.md`.*
