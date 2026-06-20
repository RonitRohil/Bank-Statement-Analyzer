# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Bank Statement Analyzer** is a full-stack application for parsing and analyzing bank statements (PDF, Excel, CSV). Users upload files through a React frontend; the backend extracts and enriches transactions with metadata (payment method, merchant, category, confidence scores), and returns structured JSON for visualization in an interactive dashboard.

- **Backend (v1 — deprecated)**: Flask 3.1.2 on port 5000 — scheduled for removal Sprint-03
- **Backend (v2 — active)**: FastAPI 0.115 on port 8000 — async, Pydantic v2, Swagger UI; all endpoints ported; frontend now points here
- **Frontend**: React 19 + TypeScript + Vite, data visualization with Recharts
- **Key Features**: Multi-format document parsing, narration analysis (UPI, IMPS, NEFT, card payments), merchant insights, confidence scoring, account metadata extraction

**Migration status (BSA-09 complete):** Frontend now points to FastAPI (port 8000). Flask (port 5000) kept for one sprint as rollback; removal scheduled Sprint-03.

## Development Setup

### Backend (Flask)

```bash
cd backend

# Create virtual environment (Windows)
python -m venv venv
venv\Scripts\activate

# Create virtual environment (macOS/Linux)
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file in /backend (example in README.md)
# Requires: FLASK_APP=run.py, FLASK_ENV=development, CORS_URLS=["http://localhost:3000"]

# Run development server (port 5000)
python run.py
# or
flask run
```

### Backend (FastAPI — backend-v2)

```bash
cd backend-v2

# Create virtual environment (Windows)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run dev server (port 8000)
uvicorn app.main:app --reload --port 8000

# Swagger UI: http://localhost:8000/docs
```

### Frontend (React + TypeScript)

```bash
cd frontend

# Install dependencies
npm install

# Create .env.local (example in .env.example)
# Requires: VITE_API_URL=http://localhost:8000  (FastAPI — active)
# Legacy: VITE_API_URL=http://localhost:5000    (Flask — deprecated, removal Sprint-03)

# Run dev server (port 3000)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Architecture

### High-Level Data Flow

```
Browser (React/TypeScript, port 3000)
    ↓ [Drag-drop file or click upload]
FileUpload component
    ↓ [FormData POST to /api/analyze/bank/statement]
FastAPI Backend (port 8000) ← active; Flask (port 5000) deprecated
    ├─ AnalyzeController: validates request, saves file to uploads/
    ├─ AnalyzeModel: routes to appropriate processor
    └─ BankStatementAnalyzer: core parsing logic
            ├─ _process_excel_csv(): handles .csv, .xlsx, .xls
            ├─ _process_pdf_transactions(): extracts PDF tables
            ├─ analyze_narration_details(): enriches transaction metadata
            ├─ calculate_confidence_score(): scores extraction quality
            └─ TransactionPatternTrainer: generates merchant insights
    ↓ [Returns JSON response]
Frontend dashboard
    ├─ AccountOverview: bank details, account holder, statement period, confidence %
    ├─ AnalyticsCharts: balance history, income vs. expense
    ├─ MerchantInsights: top merchants, frequency, amount patterns
    └─ TransactionTable: searchable transaction list with payment methods
```

### Backend Structure (Flask MVC — backend/) ⚠️ Deprecated — removal Sprint-03

| Layer       | Location                             | Purpose                                                                                |
| ----------- | ------------------------------------ | -------------------------------------------------------------------------------------- |
| Entry Point | run.py                               | Creates Flask app via create_app(), runs on port 5000 (legacy — use port 8000 FastAPI) |
| App Init    | app/**init**.py                      | Bootstraps Flask app, registers CORS, loads blueprints                                 |
| Route       | app/routes/routes.py                 | Single endpoint: POST /api/analyze/bank/statement                                      |
| Controller  | app/controllers/analyzeController.py | Handles file upload, saves to uploads/, delegates to model                             |
| Model       | app/models/analyzeModel.py           | Core business logic                                                                    |
| Config      | app/config/config.py                 | Loads CORS_URLS from .env                                                              |
| Constants   | app/constants/constants.py           | HTTP status code map                                                                   |

### Backend Structure (FastAPI — backend-v2/)

| Layer       | Location               | Purpose                                                                                       |
| ----------- | ---------------------- | --------------------------------------------------------------------------------------------- |
| Entry Point | run.py                 | Starts uvicorn on port 8000                                                                   |
| App Init    | app/main.py            | FastAPI app, CORS middleware, router registration                                             |
| Router      | app/routers/health.py  | GET /api/health                                                                               |
| Router      | app/routers/analyze.py | POST /api/analyze/bank/statement (async, to_thread)                                           |
| Model       | app/models/analyzer.py | BankStatementAnalyzer + TransactionPatternTrainer (copied from Flask, Flask imports stripped) |
| Schemas     | app/models/schemas.py  | Pydantic v2 models: Transaction, AccountInfo, AnalysisResult, AnalyzeResponse                 |
| Config      | app/config/settings.py | pydantic-settings: cors_origins, max_upload_size_mb, debug                                    |

### Core Classes in analyzeModel.py

**Active:**

- **AnalyzeModel**: Entry point; validates file path, instantiates BankStatementAnalyzer, returns JSON response
- **BankStatementAnalyzer**: Main engine
  - \_process_excel_csv(): Detects header row, normalizes columns, extracts transactions
  - \_process_pdf_transactions(): Uses pdfplumber to extract tables from PDF pages
  - detect_header_row(): Pattern-matching to identify header (looks for date, credit, debit, narration keywords)
  - find_column(): Fuzzy column matching (exact → partial match) against keyword lists
  - parse_amount(): Robust float parsing, handles currency symbols, Cr./Dr. markers, parentheses notation
  - normalize_date(): Converts multiple date formats to ISO YYYY-MM-DD
  - analyze_narration_details(): Regex-based extraction of UPI IDs, payment methods, RRN/UTR/TXN refs, banks, merchants, categories
  - calculate_confidence_score(): Scores each transaction (max 1.0) on date, amount, narration, type, receiver, balance
  - \_extract_metadata_from_text(): Regex patterns for account number, account holder, bank name, branch, IFSC, statement period

- **TransactionPatternTrainer**: Aggregates by merchant; computes count, avg/median amounts, std dev, first/last seen dates, common transaction days

**Removed dead code (all deleted — Sprint 01):**

- EnhancedNarrationAnalyzer, TransactionPatternLearner, BalanceValidator, EnhancedConfidenceScorer — incomplete stubs, never called
- verify_bank_account_with_pennyless() — hardcoded identity data, API creds undefined, never called

### Frontend Structure (React + TypeScript)

| File                            | Purpose                                                                                                                                                      |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| App.tsx                         | Root component; manages analysis state, orchestrates layout                                                                                                  |
| types.ts                        | TypeScript interfaces: AccountInfo, Transaction, AnalysisResult, ApiResponse                                                                                 |
| services/api.ts                 | uploadBankStatement(file) function; base URL from `VITE_API_URL` env var (`.env.local` sets http://localhost:8000; fallback http://localhost:5000 is legacy) |
| components/FileUpload.tsx       | Drag-drop + click file input; loading state; error alerts                                                                                                    |
| components/AccountOverview.tsx  | Bank details, account holder, confidence %, statement period                                                                                                 |
| components/AnalyticsCharts.tsx  | Recharts: balance history (line), income vs. expense (bar), top merchants (pie)                                                                              |
| components/MerchantInsights.tsx | Merchant table with counts, amounts, frequency                                                                                                               |
| components/TransactionTable.tsx | Transaction list with date, narration, payment method, amount, balance, type                                                                                 |
| components/ErrorBoundary.tsx    | Per-section error boundary                                                                                                                                   |
| index.tsx                       | React 19 DOM entry                                                                                                                                           |
| vite.config.ts                  | Vite config; dev port 3000                                                                                                                                   |

No global state manager; all data flows top-down via props.

## API Specification

### Endpoint: POST /api/analyze/bank/statement

**Request:** multipart/form-data with file field (PDF, Excel .xlsx/.xls, or CSV)

**Response (200 OK):**

```json
{
  "success": 1,
  "status_code": 200,
  "message": "N transactions parsed from [PDF|Excel/CSV]",
  "result": {
    "account_info": {
      "account_holder": "...",
      "account_number": "...",
      "bank_name": "...",
      "branch": "...",
      "ifsc_code": "...",
      "phone": null,
      "email": null,
      "statement_period": { "from": "YYYY-MM-DD", "to": "YYYY-MM-DD" }
    },
    "transactions": [
      {
        "transaction_date": "YYYY-MM-DD",
        "transaction_type": "CREDIT|DEBIT",
        "amount": 1500.50,
        "narration": "...",
        "balance": 50000.00,
        "account": null,
        "payment_method": "UPI|IMPS|NEFT|RTGS|CARD|CHEQUE|ATM|...",
        "upi_id": "user@bank|null",
        "transaction_reference": "RRN/UTR/TXN ref|null",
        "receiver_details": { "name": "...", "account": "...", "vpa": "..." },
        "bank_peer": "SBI|HDFC|...|null",
        "merchant": "AMAZON|ZOMATO|...|null",
        "category": ["E-COMMERCE", "FOOD_DELIVERY", ...],
        "remarks": ["TRANSFER", "REFUND", ...],
        "payment_gateway": "PAYTM|GOOGLE|PHONEPE|...|null",
        "confidence_score": 0.85
      }
    ],
    "confidence_summary": {
      "overall_score": 0.92,
      "total_transactions": 50,
      "high_confidence_txns": 47
    },
    "merchant_insights": {
      "AMAZON": {
        "count": 5,
        "avg_amount": 2500.00,
        "median_amount": 1999.00,
        "std_amount": 800.50,
        "first_seen": "2025-02-01",
        "last_seen": "2025-02-28",
        "common_days": [15, 20]
      }
    }
  }
}
```

## Key Algorithm Details

### Column Detection (Header Row)

1. Scan first 20 rows for keywords: date, narration, credit, debit, balance, amount, etc.
2. Accept row with ≥2 keyword matches as header
3. Fallback to row 0 if no match

### Amount Parsing

- Remove currency symbols (₹, $, €, £)
- Strip "Cr." / "Dr." suffixes
- Handle parentheses: (100) → -100
- Reject date-like formats
- Return None if parsing fails

### Date Normalization

- Detect: DD-MM-YYYY, DD/MM/YYYY, DD-Mon-YYYY, YYYY-MM-DD, etc.
- Use dayfirst=True for ambiguous dates
- Handle datetime strings with time component
- Return ISO YYYY-MM-DD; fallback to original string if unparseable

### Narration Enrichment (Regex-Based)

- **UPI**: UPI/{upi_id}/{remark}/{bank}/{txn_id} → extracts all components
- **IMPS**: IMPS/{ref}/{receiver}/{bank} → payment method, receiver, bank peer
- **VSI (Card)**: VSI/{merchant}/{datetime}/{txn_id} → merchant, payment method
- **Bank keywords**: Hardcoded list (SBI, HDFC, ICICI, AXIS, PNB, YES, KOTAK, etc.)
- **Merchants**: Hardcoded (AMAZON, ZOMATO, SWIGGY, PAYTM, PHONEPE, UBER, OLA, Netflix, etc.)
- **Categories**: Inferred from merchant (E-COMMERCE, FOOD_DELIVERY, UTILITY_BILL, INSURANCE, INVESTMENT, etc.)
- **Payment methods**: UPI, IMPS, NEFT, RTGS, BBPS, CARD, CASH, CHEQUE, ECS, SALARY, ATM, DIVIDEND, INTEREST, BILL PAY

### Confidence Score (Penalty-Based)

Starts at 1.0; penalties applied:

- Missing transaction_date: -0.25
- Missing amount: -0.25
- Missing/short narration: -0.15 / -0.05
- Missing transaction_type: -0.10
- Missing receiver details: -0.10
- Missing balance: -0.05
- Final: max(0.0, min(score, 1.0))

### Merchant Insights

For each unique merchant (or receiver if merchant not found):

- **Count**: Number of transactions
- **Amounts**: avg, median, std dev
- **Dates**: First/last occurrence
- **Common Days**: Days of month appearing >1 time

## Known Issues & Limitations

**Fixed:**

- ~~Broken Pennyless Integration~~ — deleted (TD-022, 2026-05-31)
- ~~File cleanup~~ — `finally` block deletes uploaded file after every request (both backends)
- ~~Hardcoded API URL~~ — frontend reads `VITE_API_URL` env var
- ~~Dead code classes~~ — removed (Sprint 01)
- ~~Unused scikit-learn dependency~~ — removed from requirements.txt
- ~~requirements.txt UTF-16 encoding~~ — re-encoded as UTF-8 (TD-001, 2026-05-31)
- ~~`.gitIgnore` not recognized~~ — renamed to `.gitignore`, missing patterns added (TD-020, 2026-05-31)
- ~~No `/api/health` endpoint~~ — added to Flask blueprint and FastAPI router (TD-027, 2026-05-31)

**Open:**

1. **Single Synchronous Flask Endpoint**: Large PDFs still block the Flask v1 worker thread. FastAPI v2 solves this via `asyncio.to_thread()` — migrate frontend to port 8000 (BSA-09) to close this.

2. **No Authentication**: Both backends have fully public endpoints. No auth layer planned until user accounts are in scope.

3. **PDF Limitations**: Scanned (image-based) PDFs fail silently; only works with digital/table-based PDFs. Needs OCR (Tesseract or Azure) to fix.

4. **No Balance Validation**: Running balance not validated against credit/debit deltas; inconsistent data passes through undetected.

5. **uploads/ path is process-relative**: FastAPI creates `uploads/` relative to the CWD at launch time. Always launch from `backend-v2/`.

## Common Development Tasks

### Adding a New Payment Method Detection

1. Open backend/app/models/analyzeModel.py, find analyze_narration_details() (~line 877)
2. Add keyword to payment_methods_keywords dict (~line 934) or add new regex pattern
3. Test with sample narration
4. Verify in TransactionTable UI

### Handling a New Document Format

1. Modify extract_transactions() in BankStatementAnalyzer (~line 211)
2. Add file extension check and route to appropriate processor
3. Ensure column detection and amount parsing work
4. Update FileUpload.tsx file input accept attribute
5. Update README.md

### Customizing Merchant Categories

1. Open backend/app/models/analyzeModel.py
2. Find merchants_and_categories dict (~line 1034)
3. Add/modify: "MERCHANT_NAME": {"merchant": "...", "category": "...", "payment_gateway": "..."}
4. Rebuild frontend if needed

### Debugging Parsing Issues

- Check uploads/ for uploaded file
- Review confidence_score (low score indicates quality issues)
- Trace analyze_narration_details() and \_extract_metadata_from_text() for pattern mismatches
- Use print statements in analyzeModel.py (visible in Flask console)
- For PDF: verify pdfplumber extraction with pdfplumber.open(file_path).pages[0].extract_tables()

## Testing

### Unit / Integration Tests (pytest — Flask backend)

```bash
cd backend
# activate venv first
pytest                          # run all tests (23 pass, 1 xfail)
pytest tests/test_parse_amount.py          # single test file
pytest tests/test_narration.py -v          # verbose output
pytest -k "test_upi"                       # run tests matching a pattern
```

Test files in `backend/tests/`: `test_parse_amount.py`, `test_normalize_date.py`, `test_narration.py`, `test_health.py`. Fixture for the Flask test client lives in `backend/conftest.py`.

**Known xfail:** UPI structured match returns early before merchant detection — `UPI/.../AMAZON PAY/...` yields `merchant=None`. Marked `@pytest.mark.xfail` in `test_narration.py` pending a fix.

There are currently no tests for the FastAPI backend or the React frontend.

### Manual / cURL

```bash
# FastAPI (active — port 8000)
curl -X POST http://localhost:8000/api/analyze/bank/statement \
  -F "file=@/path/to/statement.xlsx"

curl http://localhost:8000/api/health   # {"status": "ok", "service": "bank-statement-analyzer"}

# Flask (deprecated — port 5000; removal Sprint-03)
curl -X POST http://localhost:5000/api/analyze/bank/statement \
  -F "file=@/path/to/statement.xlsx"
```

### Browser

1. Start backend and frontend dev servers
2. Open http://localhost:3000
3. Upload test files
4. Check browser DevTools Network tab and Flask console

## Environment Variables

**.env (backend)**

```
FLASK_APP=run.py
FLASK_ENV=development
CORS_URLS=["http://localhost:3000"]
FLASK_DEBUG=True
```

**.env.local (frontend)**

```
VITE_API_URL=http://localhost:8000
```

(Sprint-02+: FastAPI on port 8000. Flask on port 5000 is deprecated — removal Sprint-03.)

## Technology Stack

**Backend v1 (Flask):** Flask 3.1.2, pdfplumber, pandas 2.3.3, openpyxl 3.1.5, requests 2.32.5, python-dotenv 1.2.1

**Backend v2 (FastAPI):** FastAPI 0.115.12, uvicorn, pydantic 2.11.4, pydantic-settings 2.9.1, python-multipart 0.0.20, pdfplumber, pandas 2.3.3, openpyxl 3.1.5, requests 2.32.5, python-dotenv 1.2.1

**Frontend:** React 19.2.0, TypeScript 5.8.2, Vite 6.2.0, Recharts 3.5.1, Lucide React 0.555.0, Tailwind CSS (CDN)

## Deployment Notes

- No Dockerfile or docker-compose
- No .env.example (referenced in README but missing)
- Frontend build outputs to dist/
- Backend debug mode should be disabled in production
- uploads/ directory grows unbounded; needs cleanup strategy

---

**Architecture Reference:** See [docs/architecture.md](docs/architecture.md), [docs/system-design.md](docs/system-design.md), and [docs/tech-debt.md](docs/tech-debt.md) for deeper design notes.

---

## AI Development Workflow (Claude Code + Cowork)

This project uses a two-layer AI workflow. Read this carefully before making any changes.

### Roles

| Agent             | Tool           | Responsibility                                          |
| ----------------- | -------------- | ------------------------------------------------------- |
| **Cowork Claude** | Cowork desktop | Planning, prompts, documentation, decisions, study docs |
| **Claude Code**   | CLI (`claude`) | Implementation only — writes and edits code             |

### How Changes Are Made

**Claude Code must work like a thoughtful human developer:**

1. **Read before writing.** Always read the relevant file(s) before editing. Understand what exists.
2. **Make changes in small, logical patches.** One concern per change — don't rewrite whole files unless explicitly asked.
3. **Explain each patch.** Before applying a change, state in plain English what you're changing and why.
4. **Never delete code silently.** If removing something, say what it was and why it's being removed.
5. **Follow the existing style.** Match indentation, naming conventions, and patterns already in the file.
6. **No magic.** If you're not sure, ask. Don't guess at business logic.

### Prompt Format for Claude Code

Prompts from Cowork will follow this structure:

```
## Task: [short title]

**Context:** [why this change is needed — link to tech-debt item, ADR, or sprint task]

**Files to read first:** [list of files to understand before editing]

**Change to make:**
[specific, precise description — not "improve this" but "add X to Y in Z"]

**Constraints:**
- [what NOT to do]
- [style rules]
- [what to preserve]

**Verification:**
[how to confirm the change worked — test command, expected output, etc.]
```

### Documentation Rules (mandatory)

Every change — no matter how small — must be accompanied by documentation:

| Change type           | Required doc update                                                             |
| --------------------- | ------------------------------------------------------------------------------- |
| New feature           | `docs/study/[feature-name].md` — how it works, why it was built, key code paths |
| Bug fix               | Add entry to `docs/changelog.md` with root cause and fix                        |
| Architecture decision | New `docs/adr-XXX-[title].md`                                                   |
| Requirement change    | Update `docs/requirements.md` + entry in `docs/changelog.md`                    |
| Sprint complete       | `docs/study/sprint-[N]-learnings.md` — what was built, what was learned         |
| Dependency added      | Update `docs/tech-debt.md` or `docs/architecture.md`                            |

### docs/ Folder Structure

```
docs/
  architecture.md          ← System architecture (keep updated)
  system-design.md         ← Design recommendations
  tech-debt.md             ← Prioritized backlog (mark items done as they ship)
  code-review.md           ← Code review findings
  requirements.md          ← Living requirements document
  changelog.md             ← Running log of all changes
  adr-001-*.md             ← Architecture Decision Records
  ml-ai-brainstorm.md      ← ML/AI feature roadmap
  sprint-01-plan.md        ← Sprint plans
  study/                   ← Study documents per feature/sprint
    [feature-name].md
    sprint-[N]-learnings.md
```

### Study Documents

After every sprint or significant change, a study document is written. It must cover:

1. **What was built** — feature description in plain language
2. **Why it was built** — the problem it solves
3. **How it works** — step-by-step walkthrough of the key code paths
4. **Key decisions made** — what alternatives were considered
5. **What to watch out for** — gotchas, edge cases, known limitations
6. **What's next** — follow-up work

Study docs are written for a developer who is reading this code for the first time and wants to understand it deeply — not just what it does but why every decision was made.

### Decision Log

Any change to requirements, architecture, or scope must be logged immediately in `docs/changelog.md`:

```markdown
## [Date] — [Short title]

**Type:** Requirement change | Architecture decision | Bug fix | Feature
**Decision:** [What was decided]
**Reason:** [Why]
**Impact:** [What changes as a result]
**Files affected:** [list]
```

### Sprint Cadence

- **Before sprint:** Cowork generates Claude Code prompts + updates sprint plan doc
- **During sprint:** Claude Code implements in small patches; each patch is reviewed
- **After sprint:** Study doc written, changelog updated, tech-debt.md updated (mark closed items), next sprint planned
