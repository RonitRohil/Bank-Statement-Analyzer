# System Design Report — Bank Statement Analyzer

**Date:** 2026-05-29  
**Reviewed by:** Claude (Cowork)  
**Project:** Bank Statement Analyzer (Flask + React/TypeScript)

---

## 1. Current System Design

### Request Lifecycle (Today)

```
Browser
  │
  │  POST /api/analyze/bank/statement  (multipart, sync, blocking)
  ▼
Flask (single process, debug=True)
  │
  ├── 1. Save file → uploads/{filename}
  ├── 2. Detect file type (extension)
  ├── 3. Parse (pdfplumber / pandas)         ← can take 5–30s for large files
  ├── 4. Enrich each transaction (regex loops)
  ├── 5. Score confidence per transaction
  ├── 6. Aggregate merchant insights
  └── 7. Return JSON  (can be 2–5 MB for 1000+ txns)
```

**Problems with this design:**
- One slow request blocks the entire Flask worker
- No progress feedback to the user (spinner only, no %)
- Files accumulate on disk with no TTL
- No retry mechanism — if parsing fails mid-way, client gets a 500
- Response payload grows linearly with transaction count (no pagination)

---

## 2. Recommended System Design (Near-term)

### Option A — Async Job Queue (Recommended)

Decouple file upload from processing. The upload endpoint returns a `job_id` immediately; the frontend polls for status.

```
Browser
  │
  │  POST /api/analyze/bank/statement
  ▼
Flask (upload handler)
  ├── Save file to /uploads or object storage (S3/GCS)
  └── Enqueue job → Redis / RQ / Celery
        Returns: { "job_id": "abc123", "status": "queued" }

Browser polls:
  GET /api/jobs/{job_id}
  ← { "status": "processing" | "done" | "failed", "result": {...} }

Worker Process (separate)
  ├── Dequeues job
  ├── Runs BankStatementAnalyzer
  └── Stores result in Redis (TTL: 1h) or database
```

**Why this matters:** Async design prevents timeout failures on large PDFs, allows horizontal scaling of workers, and gives users a progress indicator.

### Option B — Streaming Response (Simpler)

Keep synchronous processing but stream JSON chunks back to the browser as transactions are parsed. Lower complexity than Option A, no queue needed, but still blocks the worker thread.

---

## 3. API Design

### Current API Surface

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/analyze/bank/statement` | None | Upload + analyze statement |

### Recommended API Additions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/analyze/bank/statement` | API key | Upload file, return job_id |
| GET | `/api/jobs/{job_id}` | API key | Poll job status + result |
| GET | `/api/health` | None | Health check (liveness probe) |
| DELETE | `/api/files/{file_id}` | API key | Explicit file cleanup |

### Response Envelope

The current response shape is mostly solid. Two improvements:

1. **Pagination for transactions** — current response returns all transactions in one payload. For 3,000-row statements this is 4–6 MB of JSON. Add `page` / `page_size` query params and return `total_count` in the meta.

```json
{
  "success": 1,
  "result": {
    "account_info": {...},
    "confidence_summary": {...},
    "merchant_insights": {...},
    "transactions": [...],
    "pagination": {
      "page": 1,
      "page_size": 100,
      "total_count": 847
    }
  }
}
```

2. **Consistent error shape** — some error responses return `"errors": [str(e)]` (array), others `"message": str`. Standardize:

```json
{
  "success": 0,
  "status_code": 400,
  "message": "Human-readable summary",
  "errors": ["Detailed technical error string"]
}
```

---

## 4. File Handling Design

### Current
- Files written to `uploads/` relative to working directory
- Never deleted
- No size limit enforced
- No type validation beyond file extension

### Recommended

```
Upload phase:
  1. Validate MIME type (not just extension):
     - application/pdf
     - text/csv
     - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
     - application/vnd.ms-excel
  2. Enforce max size (e.g., 20 MB)
  3. Generate UUID filename to prevent path traversal (current code uses
     secure_filename which is good, but UUID removes guessability)
  4. Store with TTL metadata (e.g., expires_at = now + 1h)

Post-processing:
  5. Delete file immediately after analysis completes (or on failure)
  
Alternative: Stream file directly into memory (BytesIO) — no disk write at all.
             Works if files stay below ~50 MB.
```

---

## 5. Security Design

| Threat | Current State | Recommendation |
|--------|--------------|----------------|
| No authentication | API is fully open | Add API key header (`X-API-Key`) or JWT; validate on every request |
| CORS wildcard | `CORS_URLS` defaults to `"*"` | Lock to specific frontend origin in production |
| File upload abuse | No size/type limit | 20 MB max, MIME validation, UUID filenames |
| Path traversal | `secure_filename()` used ✅ | Keep; also use UUID prefix |
| Secrets in code | `INTEGRATION_AUTH` referenced but undefined | Add to `.env.example`, validate at startup |
| Debug mode in production | `debug=True` in `run.py` | Production must use `debug=False`; use gunicorn |
| Large payload DoS | No timeout | Set `UPLOAD_MAX_CONTENT_LENGTH` in Flask config; set worker timeout in gunicorn |

---

## 6. Frontend Design Considerations

### State Management
Current use of `useState` in `App.tsx` is appropriate for this scale. If the app grows (multi-statement history, user accounts, settings), migrate to `useReducer` or a lightweight state library (Zustand). Avoid Redux for this use case — overkill.

### API Client
`services/api.ts` is clean but has a hardcoded base URL. Minimum fix:

```typescript
// vite.config.ts already loads env — just use it:
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5000';
```

### Error Handling
Currently errors are string messages displayed in the FileUpload component. For a better UX as features grow:
- Distinguish between network errors, validation errors (4xx), and server errors (5xx)
- Show retry button on transient failures
- Persist last analysis result in `sessionStorage` so a page refresh doesn't lose data

### Performance
- The `TransactionTable` component renders all transactions at once. At 1,000+ rows this will stutter. Add virtual scrolling (e.g., `@tanstack/virtual`) or pagination controls.
- `AnalyticsCharts` recalculates derived data on every render. Memoize expensive aggregations with `useMemo`.

---

## 7. Scalability Path

### Phase 1 — Single Machine, Production-Ready
- Switch `run.py` to gunicorn with 4 workers: `gunicorn -w 4 -b 0.0.0.0:5000 run:app`
- Add `UPLOAD_MAX_CONTENT_LENGTH = 20 * 1024 * 1024` to Config
- Fix CORS to allow only the known frontend origin
- Delete uploaded files after processing

### Phase 2 — Async Processing
- Add Redis + Celery (or RQ)
- Move `BankStatementAnalyzer` logic into Celery tasks
- Add `GET /api/jobs/{job_id}` polling endpoint
- Store results in Redis with 1h TTL

### Phase 3 — Persistence + Multi-User
- Add PostgreSQL for storing analysis history per user
- Add user auth (FastAPI + OAuth2 or Flask-Login)
- Store files in S3/GCS (remove local disk dependency entirely)
- Add a CDN for the React build

---

## 8. Observability

Currently there is no structured observability. The app uses `print()` statements for all logging.

**Minimum viable observability stack:**

| Layer | Tool | What to track |
|-------|------|---------------|
| Logging | Python `logging` module (replace `print`) | Request ID, file type, transaction count, parse duration |
| Error tracking | Sentry (free tier) | Unhandled exceptions with stack traces |
| Health check | `GET /api/health` endpoint | Returns 200 if app is up |
| Metrics (later) | Prometheus + Grafana | p95 parse time, error rate, file upload size distribution |

---

*See `tech-debt.md` for a prioritized backlog and `code-review.md` for specific line-level issues.*
