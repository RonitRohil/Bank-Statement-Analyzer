# Technical Debt Report — Bank Statement Analyzer

**Date:** 2026-05-29  
**Reviewed by:** Claude (Cowork)  
**Project:** Bank Statement Analyzer (Flask + React/TypeScript)

Severity scale: 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low

---

## Priority 1 — Fix Before Any Production Use

### TD-001 🔴 `requirements.txt` is UTF-16 encoded
**File:** `backend/requirements.txt`  
**Problem:** The file was saved in UTF-16 (evidenced by null bytes between every character). Running `pip install -r requirements.txt` on any standard Python environment will fail silently or produce garbled output.  
**Fix:** Re-export the requirements file as plain UTF-8:
```bash
pip freeze > requirements.txt
```
Or manually recreate with only the direct dependencies (not the full freeze):
```
Flask==3.1.2
flask-cors==6.0.1
python-dotenv==1.2.1
pdfplumber==0.11.8
pandas==2.3.3
openpyxl==3.1.5
requests==2.32.5
scikit-learn==1.7.2
```

---

### TD-002 🔴 `Config.INTEGRATION_URL` and `Config.INTEGRATION_AUTH` are undefined
**File:** `backend/app/config/config.py`, `backend/app/models/analyzeModel.py`  
**Problem:** `verify_bank_account_with_pennyless()` references `Config.INTEGRATION_URL` and `Config.INTEGRATION_AUTH`, but neither is defined in the `Config` class. Any code path that calls this method raises `AttributeError` at runtime.  
**Fix:** Add to `Config` class:
```python
class Config:
    CORS_URLS = os.getenv("CORS_URLS", "*")
    INTEGRATION_URL = os.getenv("INTEGRATION_URL", "")
    INTEGRATION_AUTH = os.getenv("INTEGRATION_AUTH", "")
```
And add both keys to a `.env.example` file.

---

### TD-003 🔴 No `.env.example` file
**Problem:** There is no `.env.example` or documentation of required environment variables. A new developer has no idea what to set. The app starts with silent misconfiguration (CORS wildcard, missing integration credentials).  
**Fix:** Create `backend/.env.example`:
```
CORS_URLS=http://localhost:3000
INTEGRATION_URL=https://your-verification-api.example.com
INTEGRATION_AUTH=Bearer your_token_here
```

---

### TD-004 🔴 `debug=True` in `run.py`
**File:** `backend/run.py`  
**Problem:** `app.run(debug=True)` enables the Werkzeug debugger (exposes an interactive console on error), auto-reloader, and verbose tracebacks in HTTP responses. This is a security vulnerability in any non-local environment.  
**Fix:**
```python
if __name__ == '__main__':
    app.run(port=5000, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
```
And for production, use gunicorn: `gunicorn -w 4 -b 0.0.0.0:5000 run:app`

---

### TD-005 🔴 Uploaded files never deleted
**File:** `backend/app/controllers/analyzeController.py`  
**Problem:** Files are saved to `uploads/` and never removed. Every uploaded statement accumulates on disk forever. This includes potentially sensitive financial data.  
**Fix:** Delete the file after analysis (in a `finally` block):
```python
try:
    result, status_code = analyzer.bank_statement_analysis(data)
    return result, status_code
finally:
    if os.path.exists(file_path):
        os.remove(file_path)
```

---

## Priority 2 — Fix Soon

### TD-006 🟠 `analyzeModel.py` is 900+ lines with four dead classes
**File:** `backend/app/models/analyzeModel.py`  
**Problem:** Four classes (`EnhancedNarrationAnalyzer`, `TransactionPatternLearner`, `BalanceValidator`, `EnhancedConfidenceScorer`) are defined but never instantiated or called. They are incomplete stubs that bloat the file and confuse readers.  
`EnhancedNarrationAnalyzer.analyze()` references `self.nlp` which is never set — calling it would raise `AttributeError`.  
**Fix:** Delete the four dead classes entirely. If they represent planned features, track them as tickets/issues instead. The file should be split regardless — see TD-007.

---

### TD-007 🟠 Business logic is monolithic — everything in one 900-line file
**File:** `backend/app/models/analyzeModel.py`  
**Problem:** `BankStatementAnalyzer` handles file-type routing, column detection, Excel parsing, PDF parsing, date normalization, narration enrichment, metadata extraction, and confidence scoring all in one class. This makes the code difficult to test, extend, or debug.  
**Fix:** Extract into separate modules:
```
backend/app/
  parsers/
    excel_parser.py      ← _process_excel_csv
    pdf_parser.py        ← _process_pdf_transactions
  enrichers/
    narration_enricher.py  ← analyze_narration_details
    date_normalizer.py     ← normalize_date
    metadata_extractor.py  ← _extract_metadata_from_text
  scorers/
    confidence_scorer.py   ← calculate_confidence_score
  analyzers/
    merchant_analyzer.py   ← TransactionPatternTrainer
```

---

### TD-008 🟠 Column detection logic is duplicated between Excel and PDF paths
**File:** `backend/app/models/analyzeModel.py`  
**Problem:** The same block of `self.find_column([...], df.columns)` calls for date, credit, debit, amount, narration, balance, and account columns appears twice — once in `_process_excel_csv` and once in `_process_pdf_transactions`. Any change to column keyword lists must be made in two places.  
**Fix:** Extract into a shared `_detect_columns(df)` method that returns a `ColumnMap` dataclass.

---

### TD-009 🟠 `sklearn` is imported but not used in any active code path
**File:** `backend/app/models/analyzeModel.py`  
**Problem:**
```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.ensemble import RandomForestClassifier
```
None of these are used anywhere in the active code. `sklearn` + `scipy` are heavy dependencies (~50 MB) that increase Docker image size and install time for no benefit.  
**Fix:** Remove the imports and remove `scikit-learn` and `scipy` from `requirements.txt` until the ML features are actually built.

---

### TD-010 🟠 API base URL hardcoded in frontend
**File:** `frontend/services/api.ts`  
**Problem:** `const API_URL = 'http://localhost:5000/api/analyze/bank/statement'` is hardcoded. Cannot point to staging or production without a code change.  
**Fix:**
```typescript
// frontend/services/api.ts
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:5000';
const API_URL = `${API_BASE}/api/analyze/bank/statement`;
```
And add to `frontend/.env.example`:
```
VITE_API_URL=http://localhost:5000
```

---

### TD-011 🟠 No input validation on file upload beyond extension check
**File:** `backend/app/controllers/analyzeController.py`  
**Problem:** Only checks `filename == ""`. No MIME type validation, no file size limit. An attacker can upload a 1 GB file, a script disguised as a PDF, or probe the server with malformed inputs.  
**Fix:**
```python
ALLOWED_EXTENSIONS = {'.pdf', '.csv', '.xlsx', '.xls'}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

ext = os.path.splitext(filename)[1].lower()
if ext not in ALLOWED_EXTENSIONS:
    return jsonify({"success": False, "message": "Unsupported file type."}), 400

uploaded_file.seek(0, 2)
size = uploaded_file.tell()
uploaded_file.seek(0)
if size > MAX_FILE_SIZE:
    return jsonify({"success": False, "message": "File too large (max 20 MB)."}), 400
```

---

## Priority 3 — Improve When Possible

### TD-012 🟡 All logging uses `print()` instead of Python's `logging` module
**Problem:** `print()` doesn't support log levels, formatters, handlers, or structured output. Makes it impossible to filter log noise in production or send logs to a collector.  
**Fix:** Replace all `print("...")` with `logger = logging.getLogger(__name__)` and appropriate `logger.debug/info/warning/error` calls.

---

### TD-013 🟡 Double assignment typo
**File:** `backend/app/models/analyzeModel.py`, inside `_process_excel_csv`  
**Problem:** `parsed_date = parsed_date = self.normalize_date(...)` — the variable is assigned twice. Harmless but sloppy; indicates a copy-paste error.  
**Fix:** `parsed_date = self.normalize_date(transaction_date_str, index)`

---

### TD-014 🟡 `txn_peer_map` and `verification_tasks` are initialized but never used
**File:** `backend/app/models/analyzeModel.py`, `_process_excel_csv`  
**Problem:**
```python
verification_tasks = []
txn_peer_map = []
```
Both are created but nothing is appended or read. Leftover scaffolding.  
**Fix:** Remove both lines.

---

### TD-015 🟡 `confidence_score` not added to transactions in the PDF path
**File:** `backend/app/models/analyzeModel.py`  
**Problem:** In `_process_excel_csv`, a loop runs after parsing to add `confidence_score` to every transaction. In `_process_pdf_transactions`, this loop is missing — PDF transactions return without a `confidence_score` field. The frontend `types.ts` declares it as required on `Transaction`.  
**Fix:** Add the confidence scoring loop to `_process_pdf_transactions` before returning, or extract it into a shared method `_enrich_with_scores(transactions)`.

---

### TD-016 🟡 No test coverage whatsoever
**Problem:** There are zero test files in the repository. No unit tests, no integration tests, no snapshot tests on the frontend.  
**Suggested starting points:**
- `test_analyzeModel.py`: unit-test `parse_amount`, `normalize_date`, `find_column`, `analyze_narration_details` with edge-case inputs
- `test_routes.py`: integration test the `/api/analyze/bank/statement` endpoint with fixture files (sample CSV/PDF)
- Frontend: Vitest + React Testing Library for `FileUpload`, `TransactionTable`

---

### TD-017 🟡 CORS defaults to wildcard `*`
**File:** `backend/app/config/config.py`  
**Problem:** `CORS_URLS = os.getenv("CORS_URLS", "*")` — if the env var isn't set, any origin can call the API with credentials. Acceptable in development but dangerous if the port is accidentally exposed.  
**Fix:** Fail loudly in production if `CORS_URLS` is not explicitly configured. Or default to `http://localhost:3000` which is safer than `*`.

---

### TD-018 🟡 `TransactionTable` renders all rows — will be slow at 1000+ transactions
**File:** `frontend/components/TransactionTable.tsx`  
**Problem:** All transactions are rendered into the DOM at once. A 1,000-row statement will render ~1,000 `<tr>` elements, causing perceptible lag.  
**Fix:** Add pagination (simple page controls) or virtualized rendering (`@tanstack/virtual`).

---

### TD-019 🟢 No Dockerfile or docker-compose
**Problem:** Running the project requires manual steps for both backend (venv, pip install, env setup) and frontend (npm install, vite dev). There is no containerized setup.  
**Fix:** Add `Dockerfile` for the backend and a `docker-compose.yml` for local development.

---

### TD-020 🟢 `__pycache__` directories should be gitignored
**File:** `.gitIgnore` (note: capitalised `I` — may not be recognized on case-sensitive filesystems)  
**Problem:** Compiled Python bytecode files (`.pyc`) are tracked in git. The `.gitIgnore` filename has a capital `I` which is invalid on Linux git — the ignore rules may not apply there.  
**Fix:** Rename to `.gitignore` (lowercase) and verify it contains `**/__pycache__/` and `*.pyc`.

---

## Summary Table

| ID | Severity | Area | Description |
|----|----------|------|-------------|
| TD-001 | 🔴 | Backend | requirements.txt UTF-16 encoded — pip install fails |
| TD-002 | 🔴 | Backend | Config.INTEGRATION_URL/AUTH undefined — AttributeError |
| TD-003 | 🔴 | Backend | No .env.example — silent misconfiguration |
| TD-004 | 🔴 | Backend | debug=True in run.py — security risk |
| TD-005 | 🔴 | Backend | Uploaded files never deleted — disk/privacy risk |
| TD-006 | 🟠 | Backend | 4 dead classes in analyzeModel.py |
| TD-007 | 🟠 | Backend | 900-line monolithic model file |
| TD-008 | 🟠 | Backend | Column detection logic duplicated |
| TD-009 | 🟠 | Backend | sklearn imported but unused — 50 MB dead weight |
| TD-010 | 🟠 | Frontend | API URL hardcoded, no env var |
| TD-011 | 🟠 | Backend | No file size/MIME validation |
| TD-012 | 🟡 | Backend | print() instead of logging module |
| TD-013 | 🟡 | Backend | Double assignment typo |
| TD-014 | 🟡 | Backend | Dead variables (txn_peer_map, verification_tasks) |
| TD-015 | 🟡 | Backend | confidence_score missing from PDF path |
| TD-016 | 🟡 | Testing | Zero test coverage |
| TD-017 | 🟡 | Backend | CORS defaults to wildcard |
| TD-018 | 🟡 | Frontend | TransactionTable renders all rows at once |
| TD-019 | 🟢 | Infra | No Dockerfile or docker-compose |
| TD-020 | 🟢 | Repo | .gitIgnore capitalised, pycache files tracked |

---

*See `code-review.md` for file-level findings with specific line references.*
