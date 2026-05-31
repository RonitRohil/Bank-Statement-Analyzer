# Claude Code Prompts — Sprint 01 Remaining Work

**Generated:** 2026-05-31  
**By:** Cowork Claude  
**Sprint:** Sprint 01 (2026-05-29 → 2026-06-12)

Execute these prompts in order. Each one is a dependency for the ones that follow it.

---

## PROMPT 1 — TD-001: Fix requirements.txt UTF-16 encoding

```
## Task: Fix requirements.txt — still UTF-16 on disk

**Context:** TD-001 was marked resolved on 2026-05-29 but the fix never landed.
`file backend/requirements.txt` returns "data" (binary), and hexdump shows null bytes
after every character — classic UTF-16-LE. `pip install -r requirements.txt` fails on
any clean environment, blocking CI, Docker, and onboarding. This is the single most
important open item and must be fixed before anything else.

**Files to read first:**
- backend/requirements.txt (just run `hexdump -C backend/requirements.txt | head` to confirm encoding)

**Change to make:**
Rewrite backend/requirements.txt as plain UTF-8 ASCII with exactly these contents
(pinned versions from the current file, confirmed correct):

Flask==3.1.2
flask-cors==6.0.1
python-dotenv==1.2.1
pdfplumber==0.11.8
pandas==2.3.3
openpyxl==3.1.5
requests==2.32.5

Use Python to write the file to guarantee encoding:
  python -c "
  deps = [
      'Flask==3.1.2',
      'flask-cors==6.0.1',
      'python-dotenv==1.2.1',
      'pdfplumber==0.11.8',
      'pandas==2.3.3',
      'openpyxl==3.1.5',
      'requests==2.32.5',
  ]
  with open('backend/requirements.txt', 'w', encoding='utf-8') as f:
      f.write('\n'.join(deps) + '\n')
  "

**Constraints:**
- Do NOT use PowerShell `>` redirection — it writes UTF-16 by default, which is the
  root cause of this bug
- Do NOT add any new dependencies; these 7 are the exact set from the last clean state
- Do NOT add comments or blank lines — keep it minimal

**Verification:**
Run these two commands and confirm both pass:
  file backend/requirements.txt
  # Must print: ASCII text  (NOT "data" or "UTF-16")

  python -c "
  with open('backend/requirements.txt', 'rb') as f:
      raw = f.read(4)
  assert raw[:2] not in (b'\xff\xfe', b'\xfe\xff'), 'Still UTF-16!'
  print('OK — UTF-8 confirmed')
  "

After verification, update docs/changelog.md with:
  ## 2026-05-31 — TD-001 Fix: requirements.txt re-encoded as UTF-8
  **Type:** Bug fix (reopened)
  **Root cause:** Fix was logged on 2026-05-29 but the file on disk was never rewritten;
  PowerShell or the editor re-saved as UTF-16-LE.
  **Fix:** Rewrote via Python open(..., encoding='utf-8') to guarantee encoding.
  **Files affected:** backend/requirements.txt, docs/changelog.md
```

---

## PROMPT 2 — TD-022 + TD-020: Delete Pennyless fn + fix .gitignore

These two are independent 5-minute fixes. Do them in the same patch.

```
## Task: Remove dead Pennyless function + fix .gitignore casing

**Context:** Two quick cleanup items from the Sprint 01 tech-debt backlog.
TD-022: `verify_bank_account_with_pennyless` is dead code (never called) that ships
hardcoded identity data (`name="stco"`, `mobile="9999999999"`). It should be deleted
until the integration is real. TD-020: The repo has `.gitIgnore` (capital I) which git
ignores on case-sensitive filesystems — `__pycache__`, `.pyc`, `venv/`, and `.env`
files may be getting tracked.

**Files to read first:**
- backend/app/models/analyzeModel.py (find verify_bank_account_with_pennyless; read
  ~20 lines around it to confirm it's truly unused before deleting)
- .gitIgnore (read current contents)

**Change 1 — analyzeModel.py:**
Delete the entire `verify_bank_account_with_pennyless` static method from
`BankStatementAnalyzer`. This includes the method definition, its docstring, and the
`requests.post` call body. Do not touch anything else in the class.

Before deleting, grep the whole file for any call sites:
  grep -n "verify_bank_account\|pennyless" backend/app/models/analyzeModel.py
If any call sites exist (there should be none), report them and do NOT delete until
confirmed safe.

**Change 2 — .gitignore:**
1. If `.gitIgnore` (capital I) exists, read its contents.
2. Create `.gitignore` (all lowercase) with those contents plus these entries if not
   already present:
     __pycache__/
     *.pyc
     *.pyo
     venv/
     .env
     uploads/
     *.egg-info/
     dist/
     .DS_Store
     node_modules/
     frontend/dist/
3. Delete `.gitIgnore` (the capital-I version).

**Constraints:**
- In analyzeModel.py: delete the method only — do not touch class structure, imports,
  or surrounding methods
- Do not rename the file being deleted — just remove it
- Match existing indentation exactly

**Verification:**
  grep -n "pennyless\|verify_bank_account" backend/app/models/analyzeModel.py
  # Must return no output

  ls -la .gitignore
  # Must exist (lowercase)

  ls .gitIgnore 2>/dev/null && echo "STILL EXISTS" || echo "Gone — good"

After verification, update docs/changelog.md with:
  ## 2026-05-31 — TD-022 + TD-020: Delete dead Pennyless fn; fix .gitignore
  **Type:** Security cleanup + repo fix
  **TD-022:** Deleted verify_bank_account_with_pennyless — dead code shipping hardcoded
  identity data (name="stco", mobile="9999999999"). Never called; Config.INTEGRATION_URL
  and INTEGRATION_AUTH are defined but the fn should not live in the codebase until the
  integration is real.
  **TD-020:** Renamed .gitIgnore → .gitignore; added missing patterns for __pycache__,
  venv/, uploads/, node_modules/.
  **Files affected:** backend/app/models/analyzeModel.py, .gitignore
```

---

## PROMPT 3 — TD-027: Add GET /api/health endpoint to Flask

```
## Task: Add GET /api/health endpoint

**Context:** TD-027. No health endpoint exists. This blocks container health checks,
uptime monitoring, and is an explicit action item in adr-001-flask-vs-fastapi.md.
It's a 10-line add to the existing Flask routes file — do it now rather than waiting
for the FastAPI migration.

**Files to read first:**
- backend/app/routes/routes.py (understand the existing blueprint structure)
- backend/app/controllers/analyzeController.py (understand response pattern)
- backend/app/constants/constants.py (understand STATUS_CODES map)

**Change to make:**
Add a new route to the existing Flask blueprint in backend/app/routes/routes.py:

  @bp.route('/api/health', methods=['GET'])
  def health_check():
      return jsonify({
          "status": "ok",
          "service": "bank-statement-analyzer"
      }), 200

Import `jsonify` at the top of the file if not already imported (check first).
Do not create a new controller for this — keep it inline in routes.py since it has
no business logic.

**Constraints:**
- Do NOT add timestamp, version, or uptime fields — keep it minimal; those can be
  added later
- Do NOT touch analyzeController.py
- Match the existing import style and indentation in routes.py
- The route must be on the blueprint (bp), not on the Flask app object directly

**Verification:**
Start the Flask dev server and run:
  curl http://localhost:5000/api/health
  # Expected: {"service": "bank-statement-analyzer", "status": "ok"}  HTTP 200

If you can't start the server (environment), at minimum confirm:
  grep -n "health" backend/app/routes/routes.py
  # Must show the new route

After verification, update docs/changelog.md with:
  ## 2026-05-31 — TD-027: Add GET /api/health endpoint
  **Type:** Feature (monitoring)
  **Change:** Added /api/health route returning {"status": "ok", "service": "..."}
  **Reason:** Unblocks container health checks and uptime monitoring. Explicit ADR
  action item.
  **Files affected:** backend/app/routes/routes.py, docs/changelog.md
```

---

## PROMPT 4 — TD-016: Stand up pytest with core unit tests

```
## Task: Stand up pytest with unit tests for core parsing functions

**Context:** TD-016. Zero test coverage. This is a prerequisite for the FastAPI
migration — we cannot safely port BankStatementAnalyzer without tests to confirm
parity. Focus on the three functions most likely to break during migration:
parse_amount, normalize_date, and analyze_narration_details. Also add one integration
smoke test for the Flask endpoint.

**Files to read first:**
- backend/app/models/analyzeModel.py — find parse_amount (~line 400), normalize_date
  (~line 450), analyze_narration_details (~line 877). Read each function fully to
  understand expected inputs/outputs before writing tests.
- backend/requirements.txt — confirm pytest is not already listed

**Changes to make:**

1. Add pytest and pytest-flask to backend/requirements.txt:
   pytest==8.3.5
   pytest-flask==1.3.0

2. Create backend/tests/__init__.py (empty file).

3. Create backend/tests/test_parse_amount.py with these test cases:
   - "1,234.56" → 1234.56
   - "₹ 50,000.00" → 50000.0
   - "1500.00 Cr." → 1500.0  (positive; Cr. stripped)
   - "750.00 Dr." → 750.0   (positive; Dr. stripped — type is handled separately)
   - "(200.00)" → -200.0    (parentheses notation)
   - "0.00" → 0.0
   - "" → None
   - "N/A" → None
   - "01/02/2025" → None    (date-like string must be rejected)
   Instantiate BankStatementAnalyzer with a dummy file path and call
   self.instance.parse_amount(value). Use pytest.mark.parametrize.

4. Create backend/tests/test_normalize_date.py with these test cases:
   - "01-02-2025" → "2025-02-01"
   - "01/02/2025" → "2025-02-01"
   - "01-Feb-2025" → "2025-02-01"
   - "2025-02-01" → "2025-02-01"  (already ISO, pass through)
   - "01 Feb 2025" → "2025-02-01"
   - "" → ""   (empty string returns empty string or original)
   - "not a date" → "not a date"  (unparseable returns original)
   Use pytest.mark.parametrize.

5. Create backend/tests/test_narration.py with these test cases for
   analyze_narration_details:
   - UPI narration: "UPI/123456789012/Payment/HDFC/TXN001"
     → payment_method="UPI", bank_peer contains "HDFC"
   - IMPS narration: "IMPS/987654321098/JOHN DOE/SBI"
     → payment_method="IMPS", bank_peer contains "SBI"
   - Amazon debit: "UPI/000000000000/AMAZON PAY/HDFC/XYZ"
     → merchant contains "AMAZON"
   - Empty narration: ""
     → returns a dict with no crash (all fields null/empty)
   Assert specific keys exist in the returned dict: payment_method, upi_id,
   transaction_reference, receiver_details, bank_peer, merchant, category.

6. Create backend/conftest.py (at backend/ root, not inside tests/):
   import pytest
   from app import create_app

   @pytest.fixture
   def app():
       app = create_app()
       app.config['TESTING'] = True
       return app

   @pytest.fixture
   def client(app):
       return app.test_client()

7. Create backend/tests/test_health.py:
   def test_health_endpoint(client):
       resp = client.get('/api/health')
       assert resp.status_code == 200
       data = resp.get_json()
       assert data['status'] == 'ok'

**Constraints:**
- Do NOT write tests for dead code or anything outside the 3 core functions + health
- Do NOT mock BankStatementAnalyzer internals — call the real methods
- Instantiate BankStatementAnalyzer with a valid (but dummy/non-existent) file path
  for unit tests — it won't parse a file, just call the method
- Keep test functions short and readable — one assert per parametrize case is fine
- Do not add fixtures CSV/PDF files yet — that's a follow-up task

**Verification:**
From backend/ directory (with venv active):
  pip install pytest pytest-flask
  python -m pytest tests/ -v

All tests must pass (or explicitly document which ones fail and why, do not silently
skip). At minimum, test_parse_amount and test_normalize_date must be green.

After verification, update docs/changelog.md with:
  ## 2026-05-31 — TD-016: Stand up pytest with core unit tests
  **Type:** Testing infrastructure
  **Change:** Added pytest + pytest-flask; test suites for parse_amount, normalize_date,
  analyze_narration_details, and /api/health. Added conftest.py with Flask test client.
  **Files affected:** backend/requirements.txt, backend/conftest.py,
  backend/tests/__init__.py, backend/tests/test_parse_amount.py,
  backend/tests/test_normalize_date.py, backend/tests/test_narration.py,
  backend/tests/test_health.py
```

---

## PROMPT 5 — BSA-02: FastAPI scaffold (backend-v2/)

**Prerequisite: Prompts 1–4 must be complete first.**

```
## Task: Scaffold FastAPI backend in backend-v2/

**Context:** BSA-02 from sprint-01-plan.md. We're migrating from Flask to FastAPI
(see docs/adr-001-flask-vs-fastapi.md for full rationale). This prompt creates the
scaffold only — no business logic yet. Flask continues running on port 5000; FastAPI
will run on port 8000. The goal is: FastAPI app boots, /api/health returns 200, and
Pydantic models mirror the existing TypeScript types in frontend/src/types.ts.

**Files to read first:**
- docs/adr-001-flask-vs-fastapi.md (full decision context)
- frontend/src/types.ts (AccountInfo, Transaction, AnalysisResult — mirror these in
  Pydantic)
- backend/app/models/analyzeModel.py (skim the JSON response shape at the top — look
  for what fields get returned)
- backend/requirements.txt (understand current deps before adding new ones)

**Changes to make:**

1. Create backend-v2/ directory structure:
   backend-v2/
     app/
       __init__.py
       main.py
       models/
         __init__.py
         schemas.py
       routers/
         __init__.py
         health.py
       config/
         __init__.py
         settings.py
     requirements.txt
     run.py
     .env.example

2. backend-v2/requirements.txt (UTF-8, no BOM — use Python to write, not PowerShell):
   fastapi==0.115.12
   uvicorn[standard]==0.34.2
   python-multipart==0.0.20
   pydantic==2.11.4
   pydantic-settings==2.9.1
   python-dotenv==1.2.1
   pdfplumber==0.11.8
   pandas==2.3.3
   openpyxl==3.1.5
   requests==2.32.5

3. backend-v2/app/config/settings.py — use pydantic-settings BaseSettings:
   from pydantic_settings import BaseSettings
   from typing import list

   class Settings(BaseSettings):
       cors_origins: list[str] = ["http://localhost:3000"]
       max_upload_size_mb: int = 20
       debug: bool = False

       model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

   settings = Settings()

4. backend-v2/app/models/schemas.py — Pydantic v2 models mirroring frontend/src/types.ts:
   Define these models (field names must match the JSON keys in the Flask response exactly):
   - StatementPeriod: from_date (alias "from"), to_date (alias "to") — both Optional[str]
   - AccountInfo: account_holder, account_number, bank_name, branch, ifsc_code,
     phone, email — all Optional[str]; statement_period: Optional[StatementPeriod]
   - ReceiverDetails: name, account, vpa — all Optional[str]
   - Transaction: transaction_date, narration, payment_method, upi_id,
     transaction_reference, bank_peer, merchant, category (List[str]),
     remarks (List[str]), payment_gateway — Optional[str] for most;
     amount (Optional[float]), balance (Optional[float]),
     confidence_score (Optional[float]),
     transaction_type (Optional[str]),
     receiver_details (Optional[ReceiverDetails])
   - ConfidenceSummary: overall_score (float), total_transactions (int),
     high_confidence_txns (int)
   - AnalysisResult: account_info (AccountInfo), transactions (List[Transaction]),
     confidence_summary (ConfidenceSummary),
     merchant_insights (Dict[str, Any])
   - AnalyzeResponse: success (int), status_code (int), message (str),
     result (AnalysisResult)
   - ErrorResponse: success (int) = 0, status_code (int), message (str),
     details (Optional[str]) = None

5. backend-v2/app/routers/health.py:
   from fastapi import APIRouter
   router = APIRouter()

   @router.get("/api/health")
   def health_check():
       return {"status": "ok", "service": "bank-statement-analyzer-v2"}

6. backend-v2/app/main.py:
   - Create FastAPI app with title, description, version
   - Add CORSMiddleware using settings.cors_origins
   - Include the health router
   - Add a startup log message

7. backend-v2/app/__init__.py — just expose `create_app()`:
   from .main import app
   def create_app():
       return app

8. backend-v2/run.py:
   import uvicorn
   from app.main import app
   if __name__ == "__main__":
       uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

9. backend-v2/.env.example:
   CORS_ORIGINS=["http://localhost:3000"]
   MAX_UPLOAD_SIZE_MB=20
   DEBUG=false

**Constraints:**
- Do NOT copy any business logic from backend/ yet — that is Prompt 6
- Do NOT modify anything in backend/ — Flask stays untouched
- All Pydantic models must use model_config = {"populate_by_name": True} if using
  field aliases (needed for "from" field in StatementPeriod since "from" is a Python keyword)
- requirements.txt MUST be written via Python open(), not PowerShell redirect

**Verification:**
  cd backend-v2
  python -m venv venv && venv/Scripts/activate   # Windows
  pip install -r requirements.txt
  python run.py
  # Server starts on port 8000

  curl http://localhost:8000/api/health
  # {"status":"ok","service":"bank-statement-analyzer-v2"}

  curl http://localhost:8000/docs
  # Should return HTML (Swagger UI)

After verification, update docs/changelog.md with:
  ## 2026-05-31 — BSA-02: FastAPI scaffold (backend-v2/)
  **Type:** Feature (migration scaffold)
  **Change:** Created backend-v2/ with FastAPI app, pydantic-settings config, Pydantic
  schemas mirroring frontend types.ts, /api/health endpoint, Swagger UI at /docs.
  Flask backend unchanged and still running on port 5000.
  **Files affected:** backend-v2/ (new directory — all files)

Also update docs/adr-001-flask-vs-fastapi.md action item 1:
  - [x] Create `backend-v2/` with FastAPI scaffold
```

---

## PROMPT 6 — BSA-03: Port POST /api/analyze/bank/statement to FastAPI

**Prerequisite: Prompt 5 must be complete and backend-v2/ boots cleanly.**

```
## Task: Port /api/analyze/bank/statement to FastAPI

**Context:** BSA-03 from sprint-01-plan.md. Wrap the existing BankStatementAnalyzer
in a FastAPI route using asyncio.to_thread() so the CPU-bound parsing doesn't block
the event loop. The Flask backend stays running — we only add this endpoint to FastAPI.
Validate parity: same CSV in both → same JSON shape out.

**Files to read first:**
- backend/app/controllers/analyzeController.py (full file — understand validation +
  file handling logic to port accurately)
- backend/app/models/analyzeModel.py — specifically AnalyzeModel.analyze() and
  BankStatementAnalyzer.__init__ to understand how the file path flows in
- backend-v2/app/models/schemas.py (the Pydantic models from Prompt 5 — use these
  for response validation)
- backend-v2/app/routers/health.py (understand the router pattern to follow)
- backend-v2/app/config/settings.py (MAX_UPLOAD_SIZE_MB lives here)

**Changes to make:**

1. Copy backend/app/models/analyzeModel.py to backend-v2/app/models/analyzer.py.
   Remove the dead `verify_bank_account_with_pennyless` method if it somehow
   reappears — grep for it first.
   Do NOT modify the class logic — copy as-is.

2. Create backend-v2/app/routers/analyze.py:

   import asyncio, os, uuid, logging
   from fastapi import APIRouter, UploadFile, File, HTTPException
   from fastapi.responses import JSONResponse
   from pathlib import Path
   from app.models.analyzer import AnalyzeModel
   from app.config.settings import settings

   router = APIRouter()
   logger = logging.getLogger(__name__)
   UPLOAD_DIR = Path("uploads")
   UPLOAD_DIR.mkdir(exist_ok=True)
   ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls"}
   MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024

   @router.post("/api/analyze/bank/statement")
   async def analyze_statement(file: UploadFile = File(...)):
       # 1. Validate extension
       suffix = Path(file.filename).suffix.lower()
       if suffix not in ALLOWED_EXTENSIONS:
           raise HTTPException(status_code=400,
               detail=f"Unsupported file type: {suffix}")

       # 2. Read and validate size
       content = await file.read()
       if len(content) > MAX_BYTES:
           raise HTTPException(status_code=413,
               detail=f"File exceeds {settings.max_upload_size_mb} MB limit")

       # 3. Save to disk with UUID prefix
       unique_name = f"{uuid.uuid4().hex}{suffix}"
       file_path = UPLOAD_DIR / unique_name
       try:
           file_path.write_bytes(content)
           # 4. Run blocking analyzer in thread pool
           result = await asyncio.to_thread(
               AnalyzeModel(str(file_path)).analyze
           )
           return JSONResponse(content=result, status_code=200)
       except Exception as e:
           logger.error("Analysis failed: %s", e, exc_info=True)
           raise HTTPException(status_code=500, detail=str(e))
       finally:
           if file_path.exists():
               file_path.unlink()

   NOTE: AnalyzeModel.analyze() is called as a callable inside asyncio.to_thread —
   double-check the exact call signature from analyzeModel.py. If analyze() is a
   method (not a class with __call__), pass it as:
     result = await asyncio.to_thread(lambda: AnalyzeModel(str(file_path)).analyze())

3. Register the analyze router in backend-v2/app/main.py:
   from app.routers import health, analyze
   app.include_router(analyze.router)

4. Create uploads/ directory under backend-v2/ (or confirm the code creates it).

**Constraints:**
- Do NOT modify backend/app/models/analyzeModel.py — copy it; don't touch the original
- The blocking BankStatementAnalyzer logic MUST run inside asyncio.to_thread() — never
  call it directly in an async function without to_thread
- Always delete the uploaded file in the finally block — same pattern as Flask controller
- Match the existing Flask JSON response shape exactly (same top-level keys: success,
  status_code, message, result) — the frontend depends on this shape

**Verification:**
With backend-v2 running (python run.py):

  # Test with a real CSV file:
  curl -X POST http://localhost:8000/api/analyze/bank/statement \
    -F "file=@/path/to/test_statement.csv"
  # Must return JSON with success=1 and transactions array

  # Compare shape with Flask:
  curl -X POST http://localhost:5000/api/analyze/bank/statement \
    -F "file=@/path/to/test_statement.csv"
  # Top-level keys must match between the two responses

  # Confirm file cleanup (no orphaned files):
  ls backend-v2/uploads/
  # Must be empty after request completes

After verification, update docs/changelog.md with:
  ## 2026-05-31 — BSA-03: Port POST /api/analyze/bank/statement to FastAPI
  **Type:** Feature (migration)
  **Change:** Added /api/analyze/bank/statement to FastAPI backend. BankStatementAnalyzer
  runs in asyncio.to_thread(). File validation + cleanup mirrors Flask controller.
  Flask backend unchanged and still running.
  **Files affected:** backend-v2/app/routers/analyze.py, backend-v2/app/models/analyzer.py,
  backend-v2/app/main.py

Also update docs/adr-001-flask-vs-fastapi.md action items 3 and 4:
  - [x] Port `POST /api/analyze/bank/statement` to FastAPI
  - [x] Add `GET /api/health` endpoint

Write docs/study/fastapi-migration-sprint-01.md covering:
1. What was built (scaffold + analyze endpoint)
2. Why (see ADR-001: LLM streaming, Pydantic, DX)
3. How it works (asyncio.to_thread pattern, file lifecycle, router registration)
4. Key decisions (copy analyzer don't symlink, keep Flask alive, to_thread not Celery yet)
5. What to watch out for (to_thread must wrap ALL sync calls; don't add sync pandas
   calls in the async function body; StatementPeriod "from" alias)
6. What's next (BSA-09: full Flask cutover, BSA-04: LLM categorization, TD-016: add
   integration tests for FastAPI endpoint)
```

---

## Execution Order Summary

| # | Prompt | Debt/Sprint ID | Est. | Blocks |
|---|--------|---------------|------|--------|
| 1 | Fix requirements.txt encoding | TD-001 | 15 min | Everything |
| 2 | Delete Pennyless fn + fix .gitignore | TD-022, TD-020 | 15 min | — |
| 3 | Add /api/health to Flask | TD-027 | 15 min | — |
| 4 | Stand up pytest | TD-016 | 1–2h | BSA-02/03 (safe migration) |
| 5 | FastAPI scaffold | BSA-02 | 1.5h | BSA-03 |
| 6 | Port analyze endpoint to FastAPI | BSA-03 | 1.5h | — |

Prompts 1–3 are independent and can be run in any order (or all in one session).
Prompt 4 should be done before 5 to give you test coverage for the port.
Prompt 6 requires Prompt 5.

---

## After This Sprint

Per `docs/improvement-analysis.md`, the next sprint should start with the three
prerequisite tracks before tackling AI/ML features:

1. **Persistence layer** — SQLite to start; `accounts`, `statements`, `transactions`
   tables; de-dupe on ingest (TD-024). Unlocks anomaly detection, recurring detection,
   forecasting — half the ML roadmap assumes this exists.
2. **Evaluation harness** — `tests/fixtures/` with 15–30 anonymized statements,
   labeled expected output, and an `evaluate.py` that prints extraction accuracy +
   category precision/recall. Prerequisite for any ML/LLM work.
3. **PII redaction** — Mask account numbers, VPAs, phone numbers before any narration
   goes to a third-party LLM. Reuse existing `analyze_narration_details` extractors.

*See `docs/improvement-analysis.md` §5 for the full recommended re-sequencing.*
