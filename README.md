# Bank-Statement-Analyzer

## PDF / Excel / CSV Parser • Flask + FastAPI • React + TypeScript Frontend

This repository provides a complete bank statement analysis system. A React (TypeScript + Vite) frontend uploads statements to the backend, which extracts, normalizes, and enriches transactions from PDF, Excel, and CSV files.

**FastAPI is the active backend.** The Flask → FastAPI migration completed its frontend cutover in Sprint-02 (BSA-09):
- `backend-v2/` — **FastAPI 0.115 on port 8000 — ACTIVE.** Async, Pydantic v2, Swagger UI at `/docs`. All new development happens here.
- `backend/` — Flask 3.1.2 on port 5000 — **DEPRECATED.** Kept one sprint as a rollback; scheduled for deletion in Sprint-03 (BSA-18).

> **Status (post-Sprint-02, 2026-06-20):** the frontend points at port 8000. Two backend-only features shipped — LLM categorization (BSA-04) and a financial summary endpoint (BSA-05) — and both have known fast-follow fixes open (see `docs/tech-debt.md`, TD-033/TD-037). Full close-out in `docs/sprint-03-plan.md`.

The system detects:

- Dates
- Credit/Debit amounts
- Narration fields
- UPI IDs
- Payment methods
- Reference numbers
- Metadata (account numbers, bank name, statement period)
- Confidence score (0–1) for each transaction

This project is designed as a portfolio-grade full-stack application showcasing backend engineering, document parsing, and frontend integration.

## 🚀 Features

### 🧾 Supported Formats

- PDF (digital tables)
- Excel (.xlsx, .xls)
- CSV

### 📘 Smart Extraction

- Automatic header row detection
- Dynamic column mapping
- Date parsing (handles multiple formats)
- Amount normalization
- CR/DR identification

### 🔍 Narration Analysis

Extracts:

- UPI ID
- Payment method (UPI / IMPS / NEFT / CARD / CASH etc.)
- RRN / UTR / TXN references
- Basic merchant detection

### 🎯 Confidence Scoring

Each transaction is scored based on:
- Date correctness
- Amount accuracy
- Narration quality
- Transaction type detection

### 🧠 Metadata Extraction
- Account number
- Bank name (from PDF text)
- Statement date range

### 🖥 Frontend UI
- File upload
- Results preview
- Transaction table
- Summary view (Total credit, total debit, average confidence)

## 📁 Project Structure
```
BANK-STATEMENT-ANALYZER/
│
├── backend/                        ← Flask v1 (port 5000) — DEPRECATED (delete Sprint-03)
│   ├── app/
│   │   ├── config/
│   │   ├── constants/
│   │   ├── controllers/analyzeController.py
│   │   ├── models/analyzeModel.py
│   │   ├── routes/routes.py
│   │   └── __init__.py
│   ├── tests/                      ← pytest (23 pass, 1 xfail)
│   ├── requirements.txt
│   └── run.py
│
├── backend-v2/                     ← FastAPI v2 (port 8000) — ACTIVE
│   ├── app/
│   │   ├── config/settings.py      ← pydantic-settings (CORS, upload size, Ollama)
│   │   ├── models/
│   │   │   ├── analyzer.py         ← BankStatementAnalyzer (canonical copy)
│   │   │   └── schemas.py          ← Pydantic v2 models (incl. SummaryResponse)
│   │   ├── routers/
│   │   │   ├── health.py           ← GET  /api/health
│   │   │   ├── analyze.py          ← POST /api/analyze/bank/statement
│   │   │   └── summary.py          ← POST /api/analyze/bank/summary  (BSA-05)
│   │   ├── services/
│   │   │   └── llm_enricher.py     ← LLM category fallback via Ollama (BSA-04)
│   │   └── main.py
│   ├── tests/                      ← httpx ASGI suite (7 tests)
│   ├── requirements.txt
│   └── run.py
│
├── frontend/                       ← React + TypeScript (port 3000)
│   ├── components/
│   ├── services/api.ts
│   ├── App.tsx
│   ├── types.ts
│   ├── index.html
│   ├── package.json
│   └── .env.local                  ← VITE_API_URL=http://localhost:8000
│
├── docs/                           ← Architecture, ADRs, changelog, study docs, sprint plans, prompts
├── CLAUDE.md                       ← AI dev workflow + architecture reference
├── README.md
└── .gitignore
```


## 🛠 Backend Setup

### FastAPI backend (v2 — port 8000) — ACTIVE

``` bash
cd backend-v2
python -m venv venv
venv\Scripts\activate           # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Swagger UI at 👉 http://localhost:8000/docs

Create `backend-v2/.env` (all optional — sensible defaults exist):
```env
CORS_ORIGINS=["http://localhost:3000"]
MAX_UPLOAD_SIZE_MB=20
UVICORN_RELOAD=true             # dev only
# LLM categorization (BSA-04) — uses a local Ollama OpenAI-compatible endpoint
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

> **LLM enrichment is optional and best-effort.** If Ollama isn't running, the analyze endpoint still returns results — uncategorized transactions simply keep `category: []`.

### Flask backend (v1 — port 5000) — DEPRECATED

> Kept only as a Sprint-02 rollback; **scheduled for deletion in Sprint-03 (BSA-18).** New work should target FastAPI. Startup emits a `DeprecationWarning`.

``` bash
cd backend
python -m venv venv
venv\Scripts\activate           # Windows
pip install -r requirements.txt
python run.py
```

Create `backend/.env`:
```env
FLASK_APP=run.py
FLASK_ENV=development
CORS_URLS=["http://localhost:3000"]
FLASK_DEBUG=True
```

## 🎨 Frontend Setup (React + TypeScript)

### 1. Go to frontend folder
``` bash
cd frontend
```

### 2. Install dependencies
``` bash
npm install
```

### 3. Create .env.local
``` bash
VITE_API_URL=http://localhost:8000
```

### 4. Run frontend
``` bash
npm run dev
```

Frontend will start at:
👉 http://localhost:3000

## 📡 API Endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET`  | `/api/health` | Liveness check — `{"status": "ok", "service": "bank-statement-analyzer"}` |
| `POST` | `/api/analyze/bank/statement` | Upload a PDF/Excel/CSV → parsed + enriched transactions |
| `POST` | `/api/analyze/bank/summary` | Send a `transactions` array → income/expense/net, per-category spend, top merchants (BSA-05) |

### POST /api/analyze/bank/statement — Form-Data

| Key         | Type   | Required | Description   |
| ----------- | ------ | -------- | ------------- |
| file        | File   | Yes      | PDF/Excel/CSV |

### cURL
``` bash
# Analyze a statement (FastAPI — port 8000)
curl --location 'http://localhost:8000/api/analyze/bank/statement' \
--form 'file=@"/path/to/statement.xlsx"'

# Financial summary from the transactions array
curl --location 'http://localhost:8000/api/analyze/bank/summary' \
--header 'Content-Type: application/json' \
--data '{"transactions": [ /* the array from the analyze response */ ]}'
```

### Example Response

``` json
{
    "message": "3 transactions parsed from Excel/CSV",
    "result": {
        "account_info": {
            "account_holder": "BRAMHRISHI MISSION SAMITI",
            "account_number": "2025-03-01",
            "bank_name": "Acco",
            "branch": "BHEDAGHAT VB Drawing Power",
            "email": null,
            "ifsc_code": "SBIN0007207",
            "phone": null,
            "statement_period": {
                "from": "2025-05-02",
                "to": "2025-05-02"
            }
        },
        "confidence_summary": {
            "high_confidence_txns": 3,
            "overall_score": 1.0,
            "total_transactions": 3
        },
        "merchant_insights": {
            "38976288": {
                "avg_amount": 177.0,
                "common_days": [],
                "count": 1,
                "first_seen": "2025-02-13",
                "last_seen": "2025-02-13",
                "median_amount": 177.0,
                "std_amount": null
            },
            "IDF-XX991-CASHFREE": {
                "avg_amount": 1.0,
                "common_days": [],
                "count": 1,
                "first_seen": "2025-02-13",
                "last_seen": "2025-02-13",
                "median_amount": 1.0,
                "std_amount": null
            },
            "KMB-XX325-CASHFREE": {
                "avg_amount": 1.0,
                "common_days": [],
                "count": 1,
                "first_seen": "2025-02-05",
                "last_seen": "2025-02-05",
                "median_amount": 1.0,
                "std_amount": null
            }
        },
        "transactions": [
            {
                "account": null,
                "amount": 1.0,
                "balance": 5003.0,
                "bank_peer": "BANK ACCO--",
                "category": [],
                "confidence_score": 1.0,
                "merchant": null,
                "narration": "BY TRANSFER-INB IMPS/503618836110/kmb-XX325-Cashfree/Bank Acco--",
                "payment_gateway": null,
                "payment_method": "IMPS",
                "receiver_details": {
                    "account": null,
                    "name": "KMB-XX325-CASHFREE",
                    "vpa": null
                },
                "remarks": [
                    "IMPS TRANSFER"
                ],
                "transaction_date": "2025-02-05",
                "transaction_reference": "503618836110",
                "transaction_type": "CREDIT",
                "upi_id": null
            },
            {
                "account": null,
                "amount": 177.0,
                "balance": 4826.0,
                "bank_peer": null,
                "category": [],
                "confidence_score": 1.0,
                "merchant": null,
                "narration": "CHEQUE BOOK ISSUE CHARGE---38976288",
                "payment_gateway": null,
                "payment_method": "CHEQUE",
                "receiver_details": {
                    "account": "38976288",
                    "name": null,
                    "vpa": null
                },
                "remarks": [],
                "transaction_date": "2025-02-13",
                "transaction_reference": null,
                "transaction_type": "DEBIT",
                "upi_id": null
            },
            {
                "account": null,
                "amount": 1.0,
                "balance": 4827.0,
                "bank_peer": "BANKACCOU--",
                "category": [],
                "confidence_score": 1.0,
                "merchant": null,
                "narration": "BY TRANSFER-INB IMPS/504415336069/IDF-XX991-CASHFREE/BankAccou--",
                "payment_gateway": null,
                "payment_method": "IMPS",
                "receiver_details": {
                    "account": null,
                    "name": "IDF-XX991-CASHFREE",
                    "vpa": null
                },
                "remarks": [
                    "IMPS TRANSFER"
                ],
                "transaction_date": "2025-02-13",
                "transaction_reference": "504415336069",
                "transaction_type": "CREDIT",
                "upi_id": null
            }
        ]
    },
    "status_code": 200,
    "success": 1
}
```


## 📊 Screenshots

- Upload Screen

[Upload Screen](/screenshots/image.png)

- Result Table

[Transactions Table](/screenshots/image_1.png)

- Summary Cards

[Summary Cards](/screenshots/image_2.png)

[Summary Cards](/screenshots/image_3.png)


## 🚧 Roadmap

**Done (Sprint-01 / Sprint-02):**
- FastAPI migration (backend-v2) — analyze endpoint ported, frontend cut over to port 8000 (BSA-09)
- FastAPI integration test suite (BSA-10)
- LLM transaction categorization fallback via Ollama (BSA-04) — *fast-follow fixes open, TD-033*
- Financial summary endpoint (BSA-05)
- Multi-page PDF row stitching fix (TD-021)

**Sprint-03 (next):**
- Fix the LLM enricher + surface BSA-04/05 in the UI (summary card, AI badge)
- Delete the deprecated Flask backend (BSA-18)
- Smart stats-based insights strip (BSA-15)
- Decide & design a persistence layer (ADR-002 — SQLite/SQLModel)

**Later:**
- Month-over-month comparison, recurring/subscription detection, natural-language Q&A (need persistence)
- OCR for scanned PDFs (Tesseract / Azure Vision)
- Export to CSV/Excel
- Balance validation (detect gaps in running balance)

> Full plan: `docs/sprint-03-plan.md` · Feature exploration: `docs/feature-brainstorm.md`

## 👨‍💻 Author

**Ronit Jain**

Backend Engineer | Python | Node.js | Financial Automation | PDF/Excel Parsing

**GitHub:** https://github.com/RonitRohil

**LinkedIn:** https://www.linkedin.com/in/ronitjain0402/

**E-Mail:** ronitrohil@gmail.com

## ⭐ Support

If you like this project, give it a star ⭐ on GitHub — it motivates me to build more tools.