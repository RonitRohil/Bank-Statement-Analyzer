# Bank Statement Analyzer

## PDF / Excel / CSV Parser · FastAPI · React + TypeScript · SQLite Persistence · NL Q&A

A full-stack bank statement analysis system. Upload a statement (PDF, Excel, or CSV); the backend extracts, normalizes, and enriches transactions — payment methods, merchants, categories, confidence scores, smart insights, and recurring detection — and returns structured JSON for an interactive React dashboard. Statements are optionally persisted to SQLite for month-over-month comparison and cross-statement recurring detection.

> **Status (post-Sprint-05, 2026-06-22):** FastAPI is the sole backend. Persistence layer live (SQLite/SQLModel + Alembic). Month-over-month comparison chart shipped. Cross-statement recurring subscription detection shipped. Monolithic analyzer split into focused modules (`parsers/`, `enrichers/`, `scorers/`). ~46 tests passing. CI active on every push.

---

## Features

### Supported Formats

- PDF (digital/table-based — not scanned images)
- Excel (.xlsx, .xls)
- CSV

### Smart Extraction

- Automatic header-row detection (scans first 20 rows for keyword matches)
- Dynamic column mapping (exact → partial fuzzy match)
- Multi-format date parsing (DD-MM-YYYY, DD/MM/YYYY, DD-Mon-YYYY, ISO, etc.)
- Robust amount normalization (₹ symbols, Cr./Dr. suffixes, parentheses notation)
- Row-level duplicate detection before confidence scoring
- Multi-page PDF continuation header tracking

### Narration Analysis

- UPI IDs, payment methods (UPI / IMPS / NEFT / RTGS / CARD / ATM / CHEQUE …)
- RRN / UTR / TXN reference extraction
- Merchant detection (AMAZON, ZOMATO, NETFLIX, PAYTM, and 50+ more)
- Canonical category taxonomy — 16 labels shared by regex + LLM paths

### LLM Categorization (BSA-04)

Transactions left uncategorized by the regex analyzer are batched to a local **Ollama** endpoint (`qwen2.5:7b`). Bounded — `asyncio.Semaphore(3)` + `wait_for` global timeout. Ollama down → returns uncategorized results without failing. LLM-enriched rows flagged with an "AI" badge in the transaction table.

### Confidence Scoring

Each transaction scored 0–1 via penalty model: missing date (−0.25), missing amount (−0.25), missing narration (−0.15), missing type (−0.10), missing receiver (−0.10), missing balance (−0.05).

### Smart Insights (BSA-15)

Pure-stats callouts computed from parsed data — no LLM, zero latency. Top spending category, most frequent merchant, large transaction count, net cash flow direction, likely recurring merchants.

### Recurring Detection — Two Layers

**Single-statement (BSA-07 lite):** Identifies likely subscriptions within one statement (merchant ≥3×, CV < 0.25). Returned as `recurring_candidates`. Highlighted with a ↻ green pill in the merchant table.

**Cross-statement (BSA-07-full):** After 2+ statements for the same account are persisted, `GET /api/statements/recurring` returns merchants confirmed recurring across statements. Displayed in a Confirmed Subscriptions card with per-merchant monthly cost estimate.

### Month-over-Month Comparison (BSA-17)

`GET /api/statements/compare?account_number=XXXX` aggregates all stored statements by calendar month. Returns income, expenses, net, top category, and expense delta % per month. Frontend renders a Recharts `ComposedChart` with income/expense bars and a net trend line.

### Financial Summary (BSA-05)

`POST /api/analyze/bank/summary` → income / expenses / net, per-category breakdown, top-5 merchants. Displayed in the Spending Summary card.

### Persistence (BSA-19)

Upload with `?persist=true` to store to SQLite:

- File-hash dedup (SHA-256) — same file returns cached result instantly
- Row-level dedup — compound key removes boundary-row duplicates
- `GET /api/statements` — paginated statement list
- `GET /api/statements/{id}/transactions` — paginated transaction list for any stored statement
- Alembic migrations (`statements`, `transactions`, `corrections` tables)

### Export (BSA-13)

`POST /api/export/transactions` streams CSV or XLSX — no temp files. Filename sanitized before `Content-Disposition`. "↓ CSV" and "↓ Excel" buttons in the transaction table.

### Frontend Dashboard

- Drag-drop file upload
- Account overview (bank, holder, period, confidence %)
- Balance history, income vs. expense bar, merchant pie
- Spending Summary card
- Smart Insights strip
- Month-over-Month comparison chart
- Confirmed Subscriptions card
- Merchant insights table with ↻ recurring indicators
- Searchable transaction table with AI badge + export buttons

---

## Project Structure

```
BANK-STATEMENT-ANALYZER/
│
├── backend/                            ← FastAPI (port 8000)
│   ├── app/
│   │   ├── config/settings.py
│   │   ├── db/
│   │   │   ├── models.py               ← StatementDB, TransactionDB, CorrectionDB
│   │   │   ├── database.py
│   │   │   └── crud.py                 ← hash_file, save_statement, get_monthly_summary, get_cross_statement_recurring
│   │   ├── models/
│   │   │   ├── analyzer.py             ← BankStatementAnalyzer (thin orchestrator, 299 lines)
│   │   │   └── schemas.py
│   │   ├── parsers/                    ← split from analyzer.py (Sprint-05)
│   │   │   ├── excel_parser.py         ← process_excel_csv, parse_amount, normalize_date, find_column
│   │   │   └── pdf_parser.py           ← process_pdf_transactions, looks_like_header
│   │   ├── enrichers/
│   │   │   └── narration_enricher.py   ← analyze_narration_details
│   │   ├── scorers/
│   │   │   └── confidence_scorer.py    ← calculate_confidence_score
│   │   ├── routers/
│   │   │   ├── health.py
│   │   │   ├── analyze.py              ← POST /api/analyze/bank/statement
│   │   │   ├── summary.py              ← POST /api/analyze/bank/summary
│   │   │   ├── export.py               ← POST /api/export/transactions
│   │   │   └── statements.py           ← GET /api/statements, /compare, /recurring, /{id}/transactions
│   │   ├── services/
│   │   │   ├── categories.py           ← CANONICAL_CATEGORIES
│   │   │   ├── insights.py             ← generate_insights, detect_recurring
│   │   │   └── llm_enricher.py         ← Ollama LLM fallback
│   │   └── main.py
│   ├── alembic/
│   ├── tests/                          ← ~46 pytest tests
│   ├── requirements.txt
│   └── run.py
│
├── frontend/                           ← React 19 + TypeScript (port 3000)
│   ├── components/
│   │   ├── FileUpload.tsx, AccountOverview.tsx, AnalyticsCharts.tsx
│   │   ├── SpendingSummary.tsx, InsightsStrip.tsx
│   │   ├── MerchantInsights.tsx, TransactionTable.tsx
│   │   ├── MonthlyComparison.tsx       ← Sprint-05
│   │   ├── SubscriptionsCard.tsx       ← Sprint-05
│   │   └── ErrorBoundary.tsx
│   ├── services/api.ts
│   ├── App.tsx
│   └── types.ts
│
├── docs/                               ← Architecture, ADRs, changelog, study docs, sprint plans, Claude Code prompts
├── .github/workflows/test.yml
├── CLAUDE.md
└── .gitignore
```

---

## Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate           # Windows
# source venv/bin/activate      # macOS / Linux
pip install -r requirements.txt
alembic upgrade head            # initialize/migrate DB
uvicorn app.main:app --reload --port 8000
```

Swagger UI → http://localhost:8000/docs

**`backend/.env` (all optional):**

```env
CORS_ORIGINS=["http://localhost:3000"]
MAX_UPLOAD_SIZE_MB=20
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
DATABASE_URL=sqlite:///./statements.db
```

---

## Frontend Setup

```bash
cd frontend
npm install
echo "VITE_API_URL=http://localhost:8000" > .env.local
npm run dev      # http://localhost:3000
```

---

## API Endpoints

| Method | Path                                         | Description                                                    |
| ------ | -------------------------------------------- | -------------------------------------------------------------- |
| `GET`  | `/api/health`                                | Liveness check                                                 |
| `POST` | `/api/analyze/bank/statement`                | Upload → parsed transactions + insights + recurring candidates |
| `POST` | `/api/analyze/bank/statement?persist=true`   | Same + stores to SQLite; SHA-256 dedup                         |
| `POST` | `/api/analyze/bank/summary`                  | Transactions → income/expense/net + category breakdown         |
| `POST` | `/api/export/transactions`                   | Transactions → streamed CSV or XLSX                            |
| `GET`  | `/api/statements`                            | Paginated list of persisted statements                         |
| `GET`  | `/api/statements/compare?account_number=X`   | Month-over-month income/expense/delta                          |
| `GET`  | `/api/statements/recurring?account_number=X` | Cross-statement confirmed recurring merchants                  |
| `GET`  | `/api/statements/{id}/transactions`          | Paginated transaction list for a stored statement              |

---

## Running Tests

```bash
cd backend
pytest              # ~46 tests
pytest -v
pytest -k "comparison"
```

---

## Roadmap

**Shipped (Sprint-01 → Sprint-05):**
Multi-format parsing · LLM categorization via Ollama · Canonical 16-category taxonomy · Financial summary + Spending Summary card · Smart Insights strip · SQLite persistence + Alembic migrations · File-hash + row-level dedup · CSV/Excel export · Single-statement + cross-statement recurring detection · Month-over-month comparison chart · Paginated statements + transactions API · Monolithic analyzer split into `parsers/` + `enrichers/` + `scorers/` · CI pipeline

**Sprint-06 (next):**
Natural-language Q&A over history (BSA-06) · Statement history UI with delete (BSA-20) · Category-correction learning loop (BSA-16) · Table pagination (TD-018) · Magic-byte upload validation (TD-023)

**Later:**
Budget/alert thresholds (BSA-21) · Docker + docker-compose (TD-019) · OCR for scanned PDFs

---

## Author

**Ronit Jain** — Backend Engineer · Python · Node.js · Financial Automation

- **GitHub:** https://github.com/RonitRohil
- **LinkedIn:** https://www.linkedin.com/in/ronitjain0402/
- **Email:** ronitrohil@gmail.com
