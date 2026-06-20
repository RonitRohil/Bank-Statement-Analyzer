# Backend — FastAPI

The active backend for Bank Statement Analyzer. Async FastAPI + Pydantic v2 on port 8000, serving the React frontend. Flask was deleted in Sprint-03 (BSA-18) — this is the only backend.

## Stack

FastAPI 0.115 · uvicorn · Pydantic 2.11 + pydantic-settings · pdfplumber · pandas · openpyxl · httpx · pytest + pytest-asyncio

## Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows  (source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

### Environment (`backend/.env` — all optional, defaults in `app/config/settings.py`)

```env
CORS_ORIGINS=["http://localhost:3000"]
MAX_UPLOAD_SIZE_MB=20
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

## Layout

| Path | Purpose |
|------|---------|
| `run.py` | uvicorn entry point |
| `app/main.py` | FastAPI app, CORS middleware, router registration, lifespan |
| `app/config/settings.py` | pydantic-settings (CORS, upload size, Ollama config) |
| `app/routers/health.py` | `GET /api/health` |
| `app/routers/analyze.py` | `POST /api/analyze/bank/statement` — async (`asyncio.to_thread`), calls LLM enricher |
| `app/routers/summary.py` | `POST /api/analyze/bank/summary` — pure-math financial summary (BSA-05) |
| `app/services/categories.py` | `CANONICAL_CATEGORIES` (16 labels) + `REGEX_TO_CANONICAL` mapping |
| `app/services/insights.py` | `generate_insights()` — pure stats callouts, no LLM |
| `app/services/llm_enricher.py` | `enrich_with_llm()` — Ollama fallback for `category=[]` rows (BSA-04) |
| `app/models/analyzer.py` | `BankStatementAnalyzer` + `TransactionPatternTrainer` (parsing engine) |
| `app/models/schemas.py` | Pydantic v2: `Transaction`, `AnalyzeResponse`, `SummaryResponse`, `AnalysisResult` |

## API

- `GET /api/health` → `{"status": "ok", "service": "bank-statement-analyzer"}`
- `POST /api/analyze/bank/statement` (multipart `file`) → transactions, confidence summary, merchant insights, insights callouts
- `POST /api/analyze/bank/summary` (`{"transactions": [...]}`) → income/expense/net, per-category spend, top merchants

```bash
curl -X POST http://localhost:8000/api/analyze/bank/statement -F "file=@statement.xlsx"
curl http://localhost:8000/api/health
```

## LLM Categorization (BSA-04)

Transactions the regex analyzer leaves uncategorized (`category=[]`) are batched (10 per batch) to a local **Ollama** OpenAI-compatible endpoint. Bounded by `asyncio.Semaphore(3)` (max 3 concurrent batches) and `asyncio.wait_for` (configurable wall-clock budget). Partial results are returned on timeout — the endpoint always responds. If Ollama is down, results come back unchanged.

The LLM prompt constrains the model to `CANONICAL_CATEGORIES` from `services/categories.py` — the same 16 labels the regex path maps to via `REGEX_TO_CANONICAL`. Both paths produce identical human-readable category labels.

## Smart Insights (BSA-15)

`generate_insights()` in `services/insights.py` is a pure function (no I/O) that returns up to 5 plain-language insight strings: top category by spend share, most frequent merchant, large transaction count, net cash flow direction, and likely recurring merchants (≥3 occurrences, coefficient of variation < 0.25).

## Tests

```bash
cd backend
pytest          # 18 tests
pytest -v       # verbose
pytest -k "test_upi"    # filter
```

Tests use `ASGITransport` (httpx in-process, no live server). CI runs on every push via `.github/workflows/test.yml`.

## Notes

- Uploaded files are deleted in a `finally` block after every request (TD-005).
- `uploads/` is created relative to this directory — safe regardless of launch CWD.
- No authentication — endpoints are public until user accounts are in scope.

---

*Architecture: `../docs/architecture.md` · Tech debt: `../docs/tech-debt.md` · AI workflow: `../CLAUDE.md`*
