# Bank Statement Analyzer

## PDF / Excel / CSV Parser · FastAPI · React + TypeScript

A full-stack bank statement analysis system. Upload a statement (PDF, Excel, or CSV); the backend extracts, normalizes, and enriches transactions — payment methods, merchants, categories, confidence scores, and smart insights — and returns structured JSON for an interactive React dashboard.

> **Status (post-Sprint-03, 2026-06-20):** FastAPI is the sole backend (Flask deleted BSA-18). LLM categorization (BSA-04) and the financial summary endpoint (BSA-05) are fully live in the UI. CI pipeline active on every push.

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

### Narration Analysis
- UPI IDs, payment methods (UPI / IMPS / NEFT / RTGS / CARD / ATM / CHEQUE …)
- RRN / UTR / TXN reference extraction
- Merchant detection (AMAZON, ZOMATO, NETFLIX, PAYTM, and 50+ more)
- Canonical category taxonomy (16 labels shared by regex + LLM paths)

### LLM Categorization (BSA-04)
Transactions the regex analyzer leaves uncategorized are batched to a local **Ollama** endpoint (`qwen2.5:7b`). Best-effort and bounded — `asyncio.Semaphore(3)` + `wait_for` timeout. If Ollama is down, results come back uncategorized rather than failing.

### Confidence Scoring
Each transaction scored 0–1 by penalty model: missing date (−0.25), missing amount (−0.25), missing narration (−0.15), missing type (−0.10), missing receiver (−0.10), missing balance (−0.05).

### Smart Insights (BSA-15)
Pure-stats callouts — no LLM, zero latency:
- Top spending category by share of spend
- Most frequent merchant
- Count of large transactions (>₹10,000)
- Net cash flow direction for the period
- Likely recurring merchants (≥3 transactions, coefficient of variation < 0.25)

### Financial Summary (BSA-05)
`POST /api/analyze/bank/summary` computes income / expenses / net, per-category spend breakdown, and top-5 merchants — authoritative backend math, not re-derived frontend estimates.

### Frontend Dashboard
- Drag-drop file upload with loading state
- Account overview (bank, holder, statement period, overall confidence %)
- Balance history chart, income vs. expense bar chart, merchant pie chart
- Spending Summary card (income / expenses / net + category + merchant breakdown)
- Smart Insights strip (pill-style callout row)
- Merchant insights table with recurring indicators
- Searchable transaction table (date, narration, method, amount, balance, type, AI badge)

---

## Project Structure

```
BANK-STATEMENT-ANALYZER/
│
├── backend/                        ← FastAPI (port 8000) — sole backend
│   ├── app/
│   │   ├── config/settings.py      ← pydantic-settings (CORS, upload size, Ollama)
│   │   ├── models/
│   │   │   ├── analyzer.py         ← BankStatementAnalyzer + TransactionPatternTrainer
│   │   │   └── schemas.py          ← Pydantic v2: Transaction, AnalyzeResponse, SummaryResponse
│   │   ├── routers/
│   │   │   ├── health.py           ← GET  /api/health
│   │   │   ├── analyze.py          ← POST /api/analyze/bank/statement
│   │   │   └── summary.py          ← POST /api/analyze/bank/summary (BSA-05)
│   │   ├── services/
│   │   │   ├── categories.py       ← CANONICAL_CATEGORIES + REGEX_TO_CANONICAL (16 labels)
│   │   │   ├── insights.py         ← generate_insights() pure function
│   │   │   └── llm_enricher.py     ← Ollama LLM fallback (BSA-04)
│   │   └── main.py
│   ├── tests/                      ← pytest ASGI suite (18 tests)
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
│   │   ├── MerchantInsights.tsx
│   │   ├── TransactionTable.tsx
│   │   └── ErrorBoundary.tsx
│   ├── services/api.ts
│   ├── App.tsx
│   ├── types.ts
│   ├── index.html
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
uvicorn app.main:app --reload --port 8000
```

Swagger UI → http://localhost:8000/docs

**Environment (`backend/.env` — all optional):**
```env
CORS_ORIGINS=["http://localhost:3000"]
MAX_UPLOAD_SIZE_MB=20
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
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

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/health` | Liveness check |
| `POST` | `/api/analyze/bank/statement` | Upload PDF/Excel/CSV → parsed + enriched transactions, insights, merchant insights |
| `POST` | `/api/analyze/bank/summary` | `{"transactions": [...]}` → income/expense/net, per-category spend, top merchants |

```bash
# Analyze a statement
curl -X POST http://localhost:8000/api/analyze/bank/statement \
  -F "file=@/path/to/statement.xlsx"

# Financial summary
curl -X POST http://localhost:8000/api/analyze/bank/summary \
  -H "Content-Type: application/json" \
  -d '{"transactions": [...]}'

# Health check
curl http://localhost:8000/api/health
```

---

## Running Tests

```bash
cd backend
pytest          # 18 tests
pytest -v       # verbose
pytest -k "test_upi"    # filter by name
```

CI runs on every push via `.github/workflows/test.yml` (pytest + requirements.txt encoding guard).

---

## Roadmap

**Done (Sprint-01 → Sprint-03):**
- FastAPI backend — analyze, summary, health endpoints
- Multi-format parsing (PDF, Excel, CSV) with header-row autodetection
- Narration enrichment — UPI, IMPS, NEFT, merchant, category, payment gateway
- LLM categorization via Ollama with bounded concurrency + timeout (BSA-04)
- Canonical 16-category taxonomy shared by regex + LLM paths
- Financial summary endpoint (BSA-05) + Spending Summary card
- Smart Insights strip (pure-stats, no LLM) (BSA-15)
- Merchant insights (count, avg/median/std amounts, recurring days)
- Confidence scoring (penalty-based, per transaction)
- CI pipeline (pytest + encoding guard)

**Sprint-04 (next):**
- SQLite persistence via SQLModel + Alembic (BSA-19)
- File-hash deduplication — no re-parsing the same statement (TD-024)
- CSV / Excel export endpoint + download button (BSA-13)
- Single-statement recurring detection with `recurring_candidates` field (BSA-07 lite)

**Later:**
- Month-over-month comparison and cross-statement recurring detection (needs persistence)
- Natural-language Q&A over transaction history
- OCR for scanned PDFs (Tesseract / Azure Vision)
- Balance validation (detect gaps in running balance)

> Full plan: `docs/sprint-04-plan.md` · Feature exploration: `docs/feature-brainstorm.md`

---

## Author

**Ronit Jain**

Backend Engineer · Python · Node.js · Financial Automation · PDF/Excel Parsing

- **GitHub:** https://github.com/RonitRohil
- **LinkedIn:** https://www.linkedin.com/in/ronitjain0402/
- **Email:** ronitrohil@gmail.com

If this project is useful, give it a ⭐ on GitHub.
