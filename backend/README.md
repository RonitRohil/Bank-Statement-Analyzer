# Backend v1 — Flask (DEPRECATED)

> **This backend is deprecated and scheduled for deletion in Sprint-03 (BSA-18).**
> The active backend is `../backend-v2/` (FastAPI, port 8000). The frontend cut over to it in Sprint-02 (BSA-09). Flask is kept only as a short-lived rollback and emits a `DeprecationWarning` on startup. **Do not build new features here.**

The original implementation: Flask MVC serving the bank-statement parser on port 5000.

## Stack

Flask 3.1.2 · pdfplumber · pandas · openpyxl · python-dotenv. Tests via pytest + pytest-flask.

## Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows  (source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
python run.py                    # port 5000
```

### Environment (`backend/.env`)

```env
FLASK_APP=run.py
FLASK_ENV=development
CORS_URLS=["http://localhost:3000"]
FLASK_DEBUG=True
```

## Layout (MVC)

| Path | Purpose |
|------|---------|
| `run.py` | Creates the app via `create_app()`; `FLASK_DEBUG` env-controlled |
| `app/__init__.py` | App factory; registers CORS + blueprints |
| `app/routes/routes.py` | `GET /api/health`, `POST /api/analyze/bank/statement` |
| `app/controllers/analyzeController.py` | File upload, save to `uploads/`, delegate to model, cleanup |
| `app/models/analyzeModel.py` | `BankStatementAnalyzer` + `TransactionPatternTrainer` (the parsing engine) |
| `app/config/config.py` | Loads CORS + upload config from `.env` |
| `app/constants/constants.py` | HTTP status map |

## Tests

```bash
cd backend
pytest                           # 23 pass, 1 xfail
pytest -k test_upi               # filter by pattern
```

Test files: `tests/test_parse_amount.py`, `test_normalize_date.py`, `test_narration.py`, `test_health.py`. Flask client fixture in `conftest.py`.

> **xfail:** the structured-UPI match returns before merchant detection, so `UPI/.../AMAZON PAY/...` yields `merchant=None`. Tracked for the Sprint-03 narration fix.

## Relationship to backend-v2

`backend-v2/app/models/analyzer.py` is a near-copy of this `analyzeModel.py` (Flask imports stripped). They're kept in sync by applying parser fixes to both — a drift risk (TD-007) that **disappears when this directory is deleted**. Once BSA-18 lands, `backend-v2` is the single source of truth.

---

*Migration record: `../docs/adr-001-flask-vs-fastapi.md` · Deletion plan: `../docs/prompts/sprint-03/05-delete-flask.md` · AI workflow: `../CLAUDE.md`*
