# Study: Flask Decommission — BSA-18

**Date:** 2026-06-20
**Sprint:** Sprint-03
**Ticket:** BSA-18 (also closes TD-001 CI guard requirement)

---

## 1. What Was Removed

The Flask backend (`backend/`) was the original v1 implementation of the Bank Statement Analyzer. It contained:

- `app/__init__.py` — Flask factory (`create_app()`)
- `app/routes/routes.py` — Blueprint for `POST /api/analyze/bank/statement`
- `app/controllers/analyzeController.py` — file upload, response shaping
- `app/models/analyzeModel.py` — core parsing logic (`BankStatementAnalyzer`, `TransactionPatternTrainer`)
- `app/config/config.py` — CORS, debug, upload limit config
- `app/constants/constants.py` — HTTP status code map
- `run.py` — Flask dev server entry point (port 5000)
- `conftest.py` + `tests/` — 23 unit tests + 1 xfail (parse_amount, normalize_date, narration)
- `requirements.txt`, `pyproject.toml`, `.env.example`, `README.md`

Also removed from `backend-v2/`:

- `tests/test_parity.py` — compared Flask/FastAPI JSON shapes; had no partner to compare against
- `markers` section from `pyproject.toml` — the `integration` marker was only used by `test_parity.py`

What was NOT removed: the FastAPI rewrite in `backend-v2/` kept a clean copy of `BankStatementAnalyzer` (in `app/models/analyzer.py`) with Flask imports stripped and async wiring added. All 23 Flask test cases have equivalents in the FastAPI suite.

---

## 2. Why Now

Flask was retained one sprint after the cutover (BSA-09, Sprint-02) as a rollback safety net. The window requirements were:

1. FastAPI suite must be green — **met** (18 tests passing)
2. Frontend cutover must hold in use — **met** (port 8000 stable since BSA-09)
3. Sprint-02 fast-follow defects must be resolved — **met** (TD-033/034/036/037 fixed in Sprint-03 prompts 01–04)

Keeping two copies of `BankStatementAnalyzer` is the textbook definition of TD-007 (monolithic duplicate). Every change to the parser would require mirroring it in two files. The longer Flask stays, the greater the drift risk.

---

## 3. What the CI Workflow Does

`.github/workflows/test.yml` was added as part of BSA-18. It has two jobs:

**`backend-v2`** (the important one):

1. Checks out the repo
2. Installs Python 3.12 + `backend-v2/requirements.txt`
3. Runs `pytest` (all tests — no `integration` gating needed now that parity test is gone)
4. Encoding guard: `file backend-v2/requirements.txt | grep -qE 'ASCII|UTF-8'` — fails CI if the file is saved as UTF-16 (the regression that happened twice, TD-001)

**`frontend`**:

1. Checks out + sets up Node 20
2. `npm ci && npm run test --if-present` — no-op until a frontend test suite is added (TD-038 area)

**Why the encoding guard on `backend-v2/requirements.txt` instead of `backend/requirements.txt`?** Flask is deleted. The original TD-001 guard targeted `backend/requirements.txt` because that's the file that silently regressed to UTF-16. We now guard the only remaining requirements file — same protection, correct path.

---

## 4. Key Decisions

**Decision: Delete, don't archive.**
The Flask code is in git history (branch `ronit`, pre-BSA-18 commits). There is no reason to keep a dead `backend-v2/archived/` copy; it would just confuse future readers. Git is the archive.

**Decision: Remove the `integration` marker from `pyproject.toml`.**
The marker was created specifically for `test_parity.py` ("tests that require both Flask and FastAPI servers running"). With parity.py gone, the marker is meaningless noise. pytest warns on unknown markers but silently passes through known-but-unused ones — removing it keeps the config clean.

**Decision: Point the CI encoding guard at `backend-v2/requirements.txt`.**
The original prompt's CI template had `file backend/requirements.txt` — correct for the original context (Flask file was the one that regressed). Since Flask is deleted, the guard was updated to `backend-v2/requirements.txt`. Same class of protection, live file.

**Decision: Drop `-m "not integration"` from the CI pytest command.**
Previously, CI would have had to exclude parity tests because they need two live servers. With parity.py deleted, `pytest` (no filter) runs all 18 tests cleanly.

---

## 5. What to Watch Out For

- **The Flask unit tests are gone.** The 23 pytest cases (`test_parse_amount.py`, `test_normalize_date.py`, `test_narration.py`, `test_health.py`) tested the Flask copy of `BankStatementAnalyzer`. Their equivalents in FastAPI are: `test_analyze.py` (route-level), `test_llm_enricher.py`, `test_summary.py`. The narration/amount/date unit-level coverage has gaps — see `docs/testing-strategy.md §3.1` for the plan.

- **The xfail case is gone.** The Flask test suite had `@pytest.mark.xfail` on `UPI/.../AMAZON PAY/...` → `merchant=None`. That bug still exists in `backend-v2/app/models/analyzer.py` — it just has no test for it. If it's ever fixed, add a unit test in `backend-v2/tests/`.

- **`backend-v2/` is now the only backend.** Any path or import that still says `backend/` is wrong and should be updated. `grep -rn "backend/" .` (excluding `.git/`) is the check.

---

## 6. What's Next

- **TD-035**: Bound LLM enrichment — global timeout + batch cap. Enrichment can currently take minutes for large statements.
- **TD-038**: Surface BSA-04/05 in the UI. LLM enrichment and the summary endpoint are invisible to users.
- **Testing-strategy.md §3.1**: Add narration/amount/date unit tests to `backend-v2/tests/` to restore coverage parity with the deleted Flask suite.
- **TD-019**: Docker + compose — unblocked now that there's only one backend to containerize.
