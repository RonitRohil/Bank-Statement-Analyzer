# Backend — FastAPI

The active backend for Bank Statement Analyzer. Async FastAPI + Pydantic v2 on port 8000, serving the React frontend. Flask was deleted in Sprint-03 (BSA-18). SQLite persistence added in Sprint-04 (BSA-19).

## Stack

FastAPI 0.115 · uvicorn · Pydantic 2.11 + pydantic-settings · SQLModel 0.0.21 · Alembic 1.13 · pdfplumber · pandas · openpyxl · httpx · pytest + pytest-asyncio

## Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows  (source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt

# Initialize the database (first run only)
alembic upgrade head

uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

### Environment (`backend/.env` — all optional, defaults in `app/config/settings.py`)

```env
CORS_ORIGINS=["http://localhost:3000"]
MAX_UPLOAD_SIZE_MB=20
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
DATABASE_URL=sqlite:///./statements.db
```

## Layout

| Path | Purpose |
|------|---------|
| `run.py` | uvicorn entry point |
| `app/main.py` | FastAPI app, CORS middleware, router registration, DB lifespan |
| `app/config/settings.py` | pydantic-settings (CORS, upload size, Ollama, database_url) |
| `app/db/models.py` | SQLModel table models: `StatementDB`, `TransactionDB`, `CorrectionDB` |
| `app/db/database.py` | Engine, `get_session` FastAPI dependency, `create_db_and_tables()` |
| `app/db/crud.py` | `hash_file()`, `find_statement_by_hash()`, `save_statement()` |
| `app/routers/health.py` | `GET /api/health` |
| `app/routers/analyze.py` | `POST /api/analyze/bank/statement` — async, `persist=true` flag, LLM enricher |
| `app/routers/summary.py` | `POST /api/analyze/bank/summary` — pure-math financial summary (BSA-05) |
| `app/routers/export.py` | `POST /api/export/transactions` — CSV/Excel streaming export (BSA-13) |
| `app/routers/statements.py` | `GET /api/statements` — list persisted statements (BSA-19) |
| `app/services/categories.py` | `CANONICAL_CATEGORIES` (16 labels) + `REGEX_TO_CANONICAL` mapping |
| `app/services/insights.py` | `generate_insights()` — pure stats callouts; `detect_recurring()` — CV-based |
| `app/services/llm_enricher.py` | `enrich_with_llm()` — Ollama fallback for `category=[]` rows (BSA-04) |
| `app/models/analyzer.py` | `BankStatementAnalyzer` + `TransactionPatternTrainer` (parsing engine) |
| `app/models/schemas.py` | Pydantic v2: `Transaction`, `AnalyzeResponse`, `SummaryResponse`, `AnalysisResult` |
| `alembic/` | Alembic migrations — `versions/9670b8f28c89_initial.py` creates 3 tables |

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Liveness check |
| `POST` | `/api/analyze/bank/statement` | Upload PDF/Excel/CSV — transactions, insights, recurring candidates |
| `POST` | `/api/analyze/bank/statement?persist=true` | Same + stores in SQLite; returns cached result on duplicate upload |
| `POST` | `/api/analyze/bank/summary` | `{"transactions": [...]}` → income/expense/net, per-category, top merchants |
| `POST` | `/api/export/transactions` | `{"transactions": [...], "format": "csv"}` → streamed CSV or XLSX |
| `GET` | `/api/statements` | List all persisted statements (ordered by upload time) |

```bash
curl -X POST http://localhost:8000/api/analyze/bank/statement -F "file=@statement.xlsx"
curl -X POST "http://localhost:8000/api/analyze/bank/statement?persist=true" -F "file=@statement.xlsx"
curl http://localhost:8000/api/statements
curl http://localhost:8000/api/health
```

## Persistence (BSA-19)

Upload with `?persist=true` to store the statement and its transactions in SQLite:

- **File-level dedup:** SHA-256 of file bytes — same file uploaded twice returns the cached result without re-parsing
- **Row-level dedup:** `_deduplicate_transactions()` in `analyzer.py` removes boundary-row duplicates (compound key: `date + amount + narration[:100] + balance`) before confidence scoring
- **3 tables:** `statements` (metadata), `transactions` (FK to statements), `corrections` (reserved for BSA-16 learning loop)
- Alembic manages schema versioning — always run `alembic upgrade head` after pulling

**Encryption:** No encryption at rest. The `.db` file contains real financial data. Users are responsible for OS-level full-disk encryption. Must be revisited before any networked or multi-user deployment.

## LLM Categorization (BSA-04)

Transactions the regex analyzer leaves uncategorized (`category=[]`) are batched (10/batch) to a local Ollama OpenAI-compatible endpoint. Bounded by `asyncio.Semaphore(3)` (max 3 concurrent batches) and `asyncio.wait_for` (configurable wall-clock budget). Partial results on timeout — the endpoint always responds. LLM-enriched rows have `llm_enriched=True` in the response.

Both regex and LLM paths produce identical human-readable labels via `CANONICAL_CATEGORIES` / `REGEX_TO_CANONICAL` in `services/categories.py`.

## Smart Insights + Recurring Detection

`generate_insights()` returns up to 5 plain-language insight strings (top category, most frequent merchant, large transaction count, net cash flow, recurring teaser). `detect_recurring()` returns a structured `recurring_candidates` list — merchants with `count ≥ 3` and CV `< 0.25` (coefficient of variation on amounts). Both are pure functions in `services/insights.py`.

## Tests

```bash
cd backend
pytest          # ~38 tests
pytest -v       # verbose
pytest -k "test_upi"    # filter
```

Tests use `ASGITransport` (httpx in-process, no live server). In-memory SQLite for persistence tests — no migration needed. CI runs on every push via `.github/workflows/test.yml`.

**Test files:** `test_health`, `test_analyze`, `test_summary`, `test_llm_enricher`, `test_insights`, `test_dedup`, `test_export`, `test_persistence`

## Notes

- Uploaded files are deleted in a `finally` block after every request (TD-005).
- `uploads/` is created relative to this directory — safe regardless of launch CWD.
- `statements.db` is created in the directory where uvicorn is launched (next to `run.py`). Back up with `cp statements.db statements.db.bak`.
- No authentication — endpoints are public until user accounts are in scope.

---

*Architecture: `../docs/architecture.md` · Tech debt: `../docs/tech-debt.md` · ADR-002: `../docs/adr-002-persistence.md` · AI workflow: `../CLAUDE.md`*
