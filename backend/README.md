# Backend v2 — FastAPI (ACTIVE)

The active backend for Bank Statement Analyzer. Async FastAPI + Pydantic v2, serving the React frontend on port 8000. This replaced the Flask backend (`../backend/`) at the BSA-09 cutover; Flask is deprecated and slated for deletion in Sprint-03 (BSA-18).

## Stack

FastAPI 0.115 · uvicorn · Pydantic 2.11 + pydantic-settings · pdfplumber · pandas · openpyxl · httpx (LLM calls + tests) · pytest + pytest-asyncio.

## Setup

```bash
cd backend-v2
python -m venv venv
venv\Scripts\activate            # Windows  (source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

### Environment (`backend-v2/.env` — all optional, defaults in `app/config/settings.py`)

```env
CORS_ORIGINS=["http://localhost:3000"]
MAX_UPLOAD_SIZE_MB=20
UVICORN_RELOAD=true                 # dev only; controlled in run.py
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

## Layout

| Path | Purpose |
|------|---------|
| `run.py` | uvicorn entry; `UVICORN_RELOAD` env-controlled (TD-028) |
| `app/main.py` | FastAPI app, CORS middleware, router registration, lifespan |
| `app/config/settings.py` | pydantic-settings (CORS, upload size, Ollama config) |
| `app/routers/health.py` | `GET /api/health` |
| `app/routers/analyze.py` | `POST /api/analyze/bank/statement` — async (`asyncio.to_thread`), calls the LLM enricher |
| `app/routers/summary.py` | `POST /api/analyze/bank/summary` — pure-math financial summary (BSA-05) |
| `app/services/llm_enricher.py` | `enrich_with_llm()` — Ollama category fallback for `category=[]` rows (BSA-04) |
| `app/models/analyzer.py` | `BankStatementAnalyzer` + `TransactionPatternTrainer` (the parsing engine) |
| `app/models/schemas.py` | Pydantic v2 models: `Transaction`, `AnalyzeResponse`, `SummaryResponse`, … |

## API

- `GET /api/health` → `{"status": "ok", "service": "bank-statement-analyzer"}`
- `POST /api/analyze/bank/statement` (multipart `file`) → parsed + enriched transactions, confidence summary, merchant insights
- `POST /api/analyze/bank/summary` (`{"transactions": [...]}`) → income/expense/net, per-category spend, top merchants, date range

```bash
curl -X POST http://localhost:8000/api/analyze/bank/statement -F "file=@statement.xlsx"
curl http://localhost:8000/api/health
```

## LLM categorization (BSA-04)

Transactions the regex analyzer leaves uncategorized (`category=[]`) are batched (10 at a time) to a local **Ollama** OpenAI-compatible endpoint. **Best-effort and non-blocking** — if Ollama is down, the endpoint still returns results unchanged. The original prompt specified Claude Haiku; the implementation pivoted to local Ollama for cost (swap by pointing `OLLAMA_BASE_URL` at any OpenAI-compatible host).

> ⚠️ **Known critical issue (TD-033):** the result index-mapping in `llm_enricher.py` is buggy, so enrichment currently no-ops silently. Fix is the first item in `docs/prompts/sprint-03/01-llm-enricher-fix.md`. Also open: TD-034 (aggregates computed before enrichment), TD-035 (unbounded/blocking enrichment), TD-036 (summary takes untyped input). See `docs/code-review.md`.

## Tests

```bash
cd backend-v2
pytest -m "not integration"        # 7 in-process httpx tests (no live server)
pytest                             # includes parity test (needs both backends running)
```

`tests/test_parity.py` is fenced behind the `integration` marker and will be removed when Flask is deleted. New test plan in `docs/testing-strategy.md`.

## Notes

- `uploads/` is created relative to this directory (`Path(__file__)...`, TD-032) — safe regardless of launch CWD. Uploaded files are deleted in a `finally` block after every request.
- No authentication — endpoints are public by design until user accounts are in scope.

---

*Architecture: `../docs/architecture.md` · Tech debt: `../docs/tech-debt.md` · AI workflow: `../CLAUDE.md`*
