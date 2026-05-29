# Architecture Report — Bank Statement Analyzer

**Date:** 2026-05-29  
**Reviewed by:** Claude (Cowork)  
**Project:** Bank Statement Analyzer (Flask + React/TypeScript)

---

## 1. Overview

Bank Statement Analyzer is a full-stack web application for parsing and visualizing bank statements (PDF, Excel, CSV). The user uploads a file through the React frontend; the Flask backend extracts transactions, enriches them with metadata (payment method, merchant, category), and returns structured JSON. The frontend renders it as an interactive dashboard.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER BROWSER                         │
│                                                             │
│  React 19 + TypeScript (Vite, port 3000)                    │
│  ┌─────────────┐  ┌──────────────────────────────────────┐  │
│  │  FileUpload  │  │  Dashboard                           │  │
│  │  Component   │  │  AccountOverview | AnalyticsCharts   │  │
│  │             │  │  MerchantInsights | TransactionTable  │  │
│  └──────┬──────┘  └──────────────────────────────────────┘  │
└─────────┼───────────────────────────────────────────────────┘
          │ HTTP POST multipart/form-data
          ▼
┌─────────────────────────────────────────────────────────────┐
│                  FLASK BACKEND (port 5000)                  │
│                                                             │
│  run.py → create_app() → Blueprint: /api                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  POST /api/analyze/bank/statement                    │   │
│  │                                                      │   │
│  │  AnalyzeController                                   │   │
│  │    └→ saves file to uploads/                         │   │
│  │    └→ AnalyzeModel.bank_statement_analysis()         │   │
│  │         └→ BankStatementAnalyzer                     │   │
│  │              ├→ _process_excel_csv()  (CSV/XLSX/XLS) │   │
│  │              └→ _process_pdf_transactions()  (PDF)   │   │
│  │                   └→ TransactionPatternTrainer        │   │
│  │                        └→ merchant_insights{}         │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  uploads/  ← files saved here (never cleaned up)           │
└─────────────────────────────────────────────────────────────┘
          │ Optional (configured via env vars — currently broken)
          ▼
┌─────────────────────────────────────────────────────────────┐
│  External: Pennyless API (bank account verification)        │
│  Config.INTEGRATION_URL + Config.INTEGRATION_AUTH           │
│  (These env vars are NOT defined in Config class — bug)     │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Backend Architecture

### Pattern
Model-View-Controller (MVC) implemented via Flask Blueprints.

| Layer | File | Responsibility |
|-------|------|----------------|
| Route | `app/routes/routes.py` | URL binding → controller method |
| Controller | `app/controllers/analyzeController.py` | Request parsing, file save, response shaping |
| Model | `app/models/analyzeModel.py` | All business logic: parsing, enrichment, scoring |
| Config | `app/config/config.py` | Environment variable loading |
| Constants | `app/constants/constants.py` | HTTP status code map |

### Classes in `analyzeModel.py`
| Class | Status | Role |
|-------|--------|------|
| `AnalyzeModel` | ✅ Used | Entry point — delegates to `BankStatementAnalyzer` |
| `BankStatementAnalyzer` | ✅ Used | Core: file parsing, column detection, narration enrichment, date normalization |
| `TransactionPatternTrainer` | ✅ Used | Merchant aggregation / insight generation |
| `EnhancedNarrationAnalyzer` | ❌ Dead code | NLP-based entity extraction — incomplete, references `self.nlp` which doesn't exist |
| `TransactionPatternLearner` | ❌ Dead code | Pattern learning skeleton — never instantiated |
| `BalanceValidator` | ❌ Dead code | Running balance validation — never instantiated |
| `EnhancedConfidenceScorer` | ❌ Dead code | Multi-signal confidence scoring — never instantiated |

### Dependencies (Backend)
- **Flask 3.1.2** — web framework
- **pdfplumber** — PDF table extraction
- **pandas** — DataFrame manipulation
- **scikit-learn** — imported (`TfidfVectorizer`, `RandomForestClassifier`, `MultiLabelBinarizer`) but **not actually used** in any active code path
- **requests** — HTTP client for Pennyless API
- **python-dotenv** — env loading

---

## 4. Frontend Architecture

### Stack
- **React 19** + **TypeScript**
- **Vite 6** as build tool (dev port 3000)
- **Recharts** for data visualization
- **Lucide React** for icons
- **Tailwind CSS** (CDN-based, inferred from class names in components)

### Component Tree
```
App.tsx
├── FileUpload       — drag-and-drop file selector + loading state
├── AccountOverview  — account metadata + confidence summary
├── AnalyticsCharts  — spending charts (Recharts)
├── MerchantInsights — merchant breakdown table
├── TransactionTable — sortable/filterable transaction list
└── ErrorBoundary    — catches render errors per section
```

### Data Flow
1. User drops/selects file → `FileUpload` calls `uploadBankStatement(file)`
2. `services/api.ts` sends `multipart/form-data` POST to `http://localhost:5000/api/analyze/bank/statement`
3. On success, `AnalysisResult` stored in `App` state
4. All child components receive data as props (no global state manager — correct for this scale)

### API Coupling
The API base URL is hardcoded as `http://localhost:5000` in `services/api.ts`. There is no environment variable, making it impossible to point to a staging or production server without a code change.

---

## 5. Data Model

### API Response Shape
```json
{
  "success": 1,
  "status_code": 200,
  "message": "N transactions parsed from PDF",
  "result": {
    "account_info": { "account_holder", "account_number", "bank_name", "branch", "ifsc_code", "phone", "email", "statement_period" },
    "transactions": [
      {
        "transaction_date": "YYYY-MM-DD",
        "transaction_type": "CREDIT|DEBIT",
        "amount": 1500.00,
        "narration": "UPI/...",
        "balance": 12000.00,
        "account": null,
        "payment_method": "UPI",
        "upi_id": "user@bank",
        "transaction_reference": "320012345678",
        "receiver_details": { "name", "account", "vpa" },
        "bank_peer": "HDFC",
        "merchant": "AMAZON",
        "category": ["E-COMMERCE"],
        "remarks": ["TRANSFER"],
        "payment_gateway": null,
        "confidence_score": 0.85
      }
    ],
    "confidence_summary": { "overall_score", "total_transactions", "high_confidence_txns" },
    "merchant_insights": {
      "AMAZON": { "count", "avg_amount", "median_amount", "std_amount", "first_seen", "last_seen", "common_days" }
    }
  }
}
```

---

## 6. Infrastructure & Deployment

| Concern | Current State |
|---------|--------------|
| Containerization | None — no Dockerfile or docker-compose |
| Environment config | `.env` file required but no `.env.example` provided |
| Process management | `python run.py` with `debug=True` — dev only |
| File storage | Local `uploads/` directory — ephemeral, never purged |
| Database | None — fully stateless |
| Authentication | None on API endpoints |
| HTTPS | Not configured |
| CORS | Defaults to `*` wildcard if `CORS_URLS` env not set |

---

## 7. Strengths

- Clean MVC separation in backend
- Good TypeScript typing on frontend (`types.ts` is comprehensive)
- ErrorBoundary per dashboard section prevents full-page crashes
- Narration enrichment logic is thorough for Indian banking formats (UPI, IMPS, NEFT, RTGS)
- Confidence scoring gives downstream consumers a quality signal

---

## 8. Architectural Risks

1. **Single synchronous endpoint** — large PDFs block the Flask worker thread. No async processing or job queue.
2. **No file cleanup** — `uploads/` grows unbounded; a busy server will fill disk.
3. **Broken Pennyless integration** — `Config.INTEGRATION_URL` and `Config.INTEGRATION_AUTH` are never defined; calling the verification path raises `AttributeError`.
4. **Dead code sprawl** — four incomplete classes inflate `analyzeModel.py` to 900+ lines and suggest unfinished roadmap items that were never removed.
5. **No authentication** — the API is fully open; anyone who can reach port 5000 can analyze files.

---

*Next: See `system-design.md` for service-level design recommendations and `tech-debt.md` for a prioritized remediation list.*
