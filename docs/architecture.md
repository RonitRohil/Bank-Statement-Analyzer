# Architecture Report — Bank Statement Analyzer

**Date:** 2026-05-29 · **Updated:** 2026-06-20 (BSA-18: Flask decommissioned)
**Reviewed by:** Claude (Cowork)
**Project:** Bank Statement Analyzer (FastAPI + React/TypeScript)

---

## 1. Overview

Bank Statement Analyzer is a full-stack web application for parsing and visualizing bank statements (PDF, Excel, CSV). The user uploads a file through the React frontend; the FastAPI backend extracts transactions, enriches them with metadata (payment method, merchant, category), and returns structured JSON. The frontend renders it as an interactive dashboard.

> **History:** A Flask backend (`backend/`) was the original v1 implementation. It was migrated to FastAPI (ADR-001, Sprint-02) and removed Sprint-03 (BSA-18, 2026-06-20). See `docs/study/flask-decommission-bsa18.md`.

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
│                  FASTAPI BACKEND (port 8000)                 │
│                                                             │
│  run.py → uvicorn → FastAPI app                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  POST /api/analyze/bank/statement                    │   │
│  │                                                      │   │
│  │  analyze.py (router)                                 │   │
│  │    └→ saves file to uploads/                         │   │
│  │    └→ AnalyzeModel.bank_statement_analysis()         │   │
│  │         └→ BankStatementAnalyzer                     │   │
│  │              ├→ _process_excel_csv()  (CSV/XLSX/XLS) │   │
│  │              └→ _process_pdf_transactions()  (PDF)   │   │
│  │                   └→ TransactionPatternTrainer        │   │
│  │                        └→ merchant_insights{}         │   │
│  │    └→ enrich_with_llm() (Ollama, BSA-04)             │   │
│  │    └→ recompute merchant_insights (post-enrich)      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  uploads/  ← files saved here, deleted after response      │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Backend Architecture

### Pattern

Router → Service → Model (FastAPI, no MVC class hierarchy; routers delegate directly to models/services).

| Layer   | File                           | Responsibility                                                   |
| ------- | ------------------------------ | ---------------------------------------------------------------- |
| Router  | `app/routers/health.py`        | `GET /api/health`                                                |
| Router  | `app/routers/analyze.py`       | `POST /api/analyze/bank/statement` — orchestrates parse + enrich |
| Router  | `app/routers/summary.py`       | `POST /api/analyze/bank/summary` — pure-math summary (BSA-05)    |
| Service | `app/services/llm_enricher.py` | `enrich_with_llm()` — Ollama category fallback (BSA-04)          |
| Model   | `app/models/analyzer.py`       | `BankStatementAnalyzer` + `TransactionPatternTrainer`            |
| Schemas | `app/models/schemas.py`        | Pydantic v2 models; all request/response types                   |
| Config  | `app/config/settings.py`       | pydantic-settings env loading                                    |

### Classes in `analyzer.py`

| Class                       | Status  | Role                                                                           |
| --------------------------- | ------- | ------------------------------------------------------------------------------ |
| `AnalyzeModel`              | ✅ Used | Entry point — delegates to `BankStatementAnalyzer`                             |
| `BankStatementAnalyzer`     | ✅ Used | Core: file parsing, column detection, narration enrichment, date normalization |
| `TransactionPatternTrainer` | ✅ Used | Merchant aggregation / insight generation                                      |

(Dead classes — `EnhancedNarrationAnalyzer`, `TransactionPatternLearner`, `BalanceValidator`, `EnhancedConfidenceScorer` — removed Sprint-01.)

### Dependencies (Backend)

- **FastAPI 0.115 + uvicorn** — async web framework
- **pdfplumber** — PDF table extraction
- **pandas** — DataFrame manipulation
- **pydantic 2.11 + pydantic-settings** — schema validation, env config
- **python-multipart** — file upload parsing
- **python-dotenv** — env loading

---

## 4. Frontend Architecture

### Stack

- **React 19** + **TypeScript**
- **Vite 6** as build tool (dev port 3000)
- **Recharts** for data visualization
- **Lucide React** for icons
- **Tailwind CSS** (CDN-based)

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
2. `services/api.ts` sends `multipart/form-data` POST to `${API_BASE}/api/analyze/bank/statement` (port 8000)
3. On success, `AnalysisResult` stored in `App` state
4. All child components receive data as props (no global state manager)

### API Coupling

The API base URL is read from `VITE_API_URL` (`.env.local`), defaulting to FastAPI on port 8000. Exported as `API_BASE` from `services/api.ts` — single source of truth; interpolated into error messages (fixed TD-037, Sprint-03).

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
        "confidence_score": 0.85,
        "llm_enriched": false
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

| Concern            | Current State                                                   |
| ------------------ | --------------------------------------------------------------- |
| Containerization   | None — no Dockerfile or docker-compose                          |
| Environment config | `.env.local` (frontend); pydantic-settings (backend)            |
| Process management | `uvicorn app.main:app --reload` — dev only                      |
| File storage       | Local `uploads/` directory — deleted post-response              |
| Database           | None — fully stateless                                          |
| Authentication     | None on API endpoints                                           |
| HTTPS              | Not configured                                                  |
| CORS               | Locked to `cors_origins` setting (default localhost)            |
| CI                 | `.github/workflows/test.yml` — pytest + encoding guard (BSA-18) |

---

## 7. Strengths

- Async FastAPI with `asyncio.to_thread()` — file parsing doesn't block the event loop
- Pydantic v2 schemas — all I/O validated at the boundary; bad inputs return 422, not 500
- ErrorBoundary per dashboard section prevents full-page crashes
- Narration enrichment logic is thorough for Indian banking formats (UPI, IMPS, NEFT, RTGS)
- Confidence scoring gives downstream consumers a quality signal
- LLM enrichment is non-blocking: Ollama down → 200 with unchanged transactions

---

## 8. Architectural Risks

1. **Single-process enrichment** — LLM enrichment runs inline inside the request; 200 uncategorized rows → minutes (TD-035).
2. **Monolithic model file** — `analyzer.py` is 1,280 lines; column detection is duplicated between PDF and CSV paths (TD-007/TD-008).
3. **No authentication** — the API is fully open (no auth planned until user accounts are in scope).
4. **No PDF OCR** — scanned (image-based) PDFs fail silently; pdfplumber only handles digital/table PDFs.

---

_Next: See `system-design.md` for service-level design recommendations and `tech-debt.md` for a prioritized remediation list._
