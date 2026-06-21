# Bank Statement Analyzer

## PDF / Excel / CSV Parser · FastAPI · React + TypeScript · SQLite Persistence

A full-stack bank statement analysis system. Upload a statement (PDF, Excel, or CSV); the backend extracts, normalizes, and enriches transactions — payment methods, merchants, categories, confidence scores, smart insights, and recurring detection — and returns structured JSON for an interactive React dashboard. Statements are optionally persisted to SQLite for month-over-month comparison.

> **Status (post-Sprint-04, 2026-06-21):** FastAPI is the sole backend. Persistence layer live (SQLite/SQLModel + Alembic). CSV/Excel export shipped. Single-statement recurring detection shipped. ~38 tests passing. CI active on every push.

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
- Row-level duplicate detection before confidence scoring (TD-024)

### Narration Analysis

- UPI IDs, payment methods (UPI / IMPS / NEFT / RTGS / CARD / ATM / CHEQUE …)
- RRN / UTR / TXN reference extraction
- Merchant detection (AMAZON, ZOMATO, NETFLIX, PAYTM, and 50+ more)
- Canonical category taxonomy (16 labels shared by regex + LLM paths)

### LLM Categorization (BSA-04)

Transactions the regex analyzer leaves uncategorized are batched to a local **Ollama** endpoint (`qwen2.5:7b`). Best-effort and bounded — `asyncio.Semaphore(3)` + `wait_for` timeout. If Ollama is down, results come back uncategorized rather than failing. LLM-enriched rows are flagged with an "AI" badge in the transaction table.

### Confidence Scoring

Each transaction scored 0–1 by penalty model: missing date (−0.25), missing amount (−0.25), missing narration (−0.15), missing type (−0.10), missing receiver (−0.10), missing balance (−0.05).

### Smart Insights (BSA-15)

Pure-stats callouts — no LLM, zero latency:

- Top spending category by share of spend
- Most frequent merchant
- Count of large transactions (>₹10,000)
- Net cash flow direction for the period
- Likely recurring merchants (≥3 transactions, coefficient of variation < 0.25)

### Recurring Detection (BSA-07 lite)

`detect_recurring()` identifies likely subscriptions within a single statement (merchant ≥3×, CV < 0.25). Returned as `recurring_candidates` in the API response. Highlighted in the merchant table with a ↻ green pill.

### Financial Summary (BSA-05)

`POST /api/analyze/bank/summary` computes income / expenses / net, per-category spend breakdown, and top-5 merchants — authoritative backend math, not re-derived frontend estimates.

### Persistence (BSA-19)

Upload with `?persist=true` to store the statement and transactions in SQLite:

- **File-hash dedup:** SHA-256 check before parsing — same file uploaded twice returns the cached result instantly
- **Row-level dedup:** `_deduplicate_transactions()` removes boundary-row duplicates before confidence scoring
- **`GET /api/statements`:** Lists all stored statements ordered by upload time
- **Alembic migrations** for schema versioning
- 3 tables: `statements`, `transactions`, `corrections` (corrections reserved for BSA-16)

### Export (BSA-13)

`POST /api/export/transactions` accepts a transactions list and streams a CSV or Excel file — no temp files written to disk. "↓ CSV" and "↓ Excel" buttons in the transaction table header.

### Frontend Dashboard

- Drag-drop file upload with loading state
- Account overview (bank, holder, statement period, overall confidence %)
- Balance history chart, income vs. expense bar chart, merchant pie chart
- Spending Summary card (income / expenses / net + category + merchant breakdown)
- Smart Insights strip (pill-style callout row)
- Merchant insights table with ↻ recurring indicators
- Searchable transaction table with AI badge on LLM-enriched rows + export buttons

---

## Project Structure

```
BANK-STATEMENT-ANALYZER/
│
├── backend/                        ← FastAPI (port 8000) — sole backend
│   ├── app/
│   │   ├── config/settings.py      ← pydantic-settings (CORS, upload size, Ollama, DB URL)
│   │   ├── db/
│   │   │   ├── models.py           ← SQLModel table models: StatementDB, TransactionDB, CorrectionDB
│   │   │   ├── database.py         ← engine, get_session, create_db_and_tables
│   │   │   └── crud.py             ← hash_file, find_statement_by_hash, save_statement
│   │   ├── models/
│   │   │   ├── analyzer.py         ← BankStatementAnalyzer + TransactionPatternTrainer
│   │   │   └── schemas.py          ← Pydantic v2: Transaction, AnalyzeResponse, SummaryResponse
│   │   ├── routers/
│   │   │   ├── health.py           ← GET  /api/health
│   │   │   ├── analyze.py          ← POST /api/analyze/bank/statement (?persist=true)
│   │   │   ├── summary.py          ← POST /api/analyze/bank/summary
│   │   │   ├── export.py           ← POST /api/export/transactions (?format=csv|xlsx)
│   │   │   └── statements.py       ← GET  /api/statements
│   │   ├── services/
│   │   │   ├── categories.py       ← CANONICAL_CATEGORIES + REGEX_TO_CANONICAL (16 labels)
│   │   │   ├── insights.py         ← generate_insights() + detect_recurring()
│   │   │   └── llm_enricher.py     ← Ollama LLM fallback (BSA-04)
│   │   └── main.py
│   ├── alembic/                    ← Alembic migrations (Sprint-04: initial 3-table schema)
│   ├── tests/                      ← pytest ASGI suite (~38 tests)
│   ├── requirements.txt
│   └── run.py
│
├── frontend/                       ← React 19 + TypeScript (port 3000)
│   ├── components/
│   │   ├── FileUpload.tsx
│   │   ├── AccountOverview.tsx
│   │   ├── AnalyticsCharts.tsx
│   │   ├── SpendingSummary.tsx     ← income/expense/net + categories + merchants (BSA-12)
│   │   ├── InsightsStrip.tsx       ← smart stats callouts (BSA-15)
│   │   ├── MerchantInsights.tsx    ← ↻ pill on recurring candidates (BSA-07 lite)
│   │   ├── TransactionTable.tsx    ← AI badge + ↓ CSV / ↓ Excel buttons (BSA-13)
│   │   └── ErrorBoundary.tsx
│   ├── services/api.ts             ← API_BASE, uploadBankStatement, getSummary, exportTransactions
│   ├── App.tsx
│   ├── types.ts
│   └── .env.local                  ← VITE_API_URL=http://localhost:8000
│
├── docs/                           ← Architecture, ADRs, changelog, study docs, sprint plans, prompts
├── .github/workflows/test.yml      ← CI: pytest + requirements.txt encoding guard
├── CLAUDE.md                       ← AI dev workflow + architecture reference
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

# Initialize the database (first run only)
alembic upgrade head

uvicorn app.main:app --reload --port 8000
```

Swagger UI → http://localhost:8000/docs

**Environment (`backend/.env` — all optional):**

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

# Create .env.local
echo "VITE_API_URL=http://localhost:8000" > .env.local

npm run dev      # http://localhost:3000
npm run build    # outputs to dist/
npm run preview  # preview production build
```

---

## API Endpoints

| Method | Path                                       | Description                                                                                             |
| ------ | ------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| `GET`  | `/api/health`                              | Liveness check                                                                                          |
| `POST` | `/api/analyze/bank/statement`              | Upload PDF/Excel/CSV → parsed + enriched transactions + insights + recurring candidates                 |
| `POST` | `/api/analyze/bank/statement?persist=true` | Same as above, but stores statement + transactions in SQLite; returns cached result on duplicate upload |
| `POST` | `/api/analyze/bank/summary`                | `{"transactions": [...]}` → income/expense/net, per-category spend, top merchants                       |
| `POST` | `/api/export/transactions`                 | `{"transactions": [...], "format": "csv"}` → streamed CSV or XLSX download                              |
| `GET`  | `/api/statements`                          | List all persisted statements (ordered by upload time)                                                  |

```bash
# Analyze and persist a statement
curl -X POST "http://localhost:8000/api/analyze/bank/statement?persist=true" \
  -F "file=@/path/to/statement.xlsx"

# Export transactions as CSV
curl -X POST http://localhost:8000/api/export/transactions \
  -H "Content-Type: application/json" \
  -d '{"transactions": [...], "format": "csv", "filename": "my-statement"}' \
  -o transactions.csv

# List stored statements
curl http://localhost:8000/api/statements

# Health check
curl http://localhost:8000/api/health
```

---

## Running Tests

```bash
cd backend
pytest          # ~38 tests
pytest -v       # verbose
pytest -k "test_upi"    # filter by name
```

CI runs on every push via `.github/workflows/test.yml` (pytest + requirements.txt encoding guard).

---

## Roadmap

**Done (Sprint-01 → Sprint-04):**

- FastAPI backend — analyze, summary, health, export, statements endpoints
- Multi-format parsing (PDF, Excel, CSV) with header-row autodetection
- Narration enrichment — UPI, IMPS, NEFT, merchant, category, payment gateway
- LLM categorization via Ollama with bounded concurrency + timeout (BSA-04)
- Canonical 16-category taxonomy shared by regex + LLM paths
- Financial summary endpoint (BSA-05) + Spending Summary card
- Smart Insights strip (pure-stats, no LLM) (BSA-15)
- Row-level duplicate transaction detection before confidence scoring
- SQLite persistence via SQLModel + Alembic — `persist=true` flag, file-hash dedup (BSA-19)
- CSV / Excel export — streaming, no temp files (BSA-13)
- Single-statement recurring detection with `recurring_candidates` field (BSA-07 lite)
- AI badge on LLM-enriched transaction rows
- Confidence scoring (penalty-based, per transaction)
- CI pipeline (pytest + encoding guard)

**Sprint-05 (next):**

- Month-over-month comparison (`GET /api/statements/compare`) (BSA-17)
- Cross-statement recurring subscription detection (BSA-07-full)
- `BankStatementAnalyzer` split into focused parser/enricher/scorer modules (TD-007/008)

**Later:**

- Natural-language Q&A over transaction history (BSA-06)
- Category-correction learning loop (BSA-16 — uses `corrections` table, already in schema)
- Table virtualization for large datasets (TD-018)
- OCR for scanned PDFs (Tesseract / Azure Vision)
- Docker + docker-compose (TD-019)

> Full plan: `docs/sprint-05-plan.md` · Feature exploration: `docs/feature-brainstorm.md` · Architecture decisions: `docs/adr-002-persistence.md`

---

## Author

**Ronit Jain**

Backend Engineer · Python · Node.js · Financial Automation · PDF/Excel Parsing

- **GitHub:** https://github.com/RonitRohil
- **LinkedIn:** https://www.linkedin.com/in/ronitjain0402/
- **Email:** ronitrohil@gmail.com

If this project is useful, give it a ⭐ on GitHub.
