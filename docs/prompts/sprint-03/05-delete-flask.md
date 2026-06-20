# Prompt: Decommission Flask + Add CI — BSA-18

**Task:** Delete the Flask backend (its rollback window is over), remove the now-pointless parity test, update docs, and add a CI workflow including the TD-001 encoding guard.
**Sprint ref:** Sprint-03 · Ticket: BSA-18 (also closes TD-001's "CI guard" requirement)
**Estimated time:** 1–2 hours
**Prerequisite:** Prompts 01–04 are merged and `cd backend-v2 && pytest -m "not integration"` is green. **Do not delete Flask until the fast-follows are verified — it's the rollback.**

---

## Why This Change Is Needed

Flask was kept one sprint as a rollback after BSA-09. The FastAPI suite is green, the cutover held in use, and the deprecation warning has been live. Keeping two copies of `BankStatementAnalyzer` guarantees drift (TD-007). Time to remove it.

## Files to Read First

1. `backend/` — the whole Flask tree to be removed
2. `backend-v2/tests/test_parity.py` — compares against Flask; becomes dead
3. `CLAUDE.md` — dual-backend framing throughout
4. `docs/architecture.md`, `docs/requirements.md` — Flask references
5. `.github/` — confirm no workflow exists yet

## Changes to Make

### 1. Delete the Flask backend
- `rm -rf backend/` (the Flask app, its `tests/`, `conftest.py`, `requirements.txt`, `.env.example`).
- Keep any genuinely shared fixtures by moving them into `backend-v2/tests/fixtures/` first if referenced.

### 2. Remove the parity test
- Delete `backend-v2/tests/test_parity.py` and the `integration` marker usage tied to it. Keep the marker definition in `pyproject.toml` only if another integration test uses it; otherwise remove it too.

### 3. Update docs (mandatory per CLAUDE.md)
- `CLAUDE.md`: collapse the dual-backend sections to FastAPI-only. Remove the "Flask deprecated / removal Sprint-03" notes (it's done). Keep a one-line history note.
- `docs/architecture.md`: drop the Flask column/table; FastAPI is *the* backend.
- `docs/requirements.md`: remove Flask env vars / port 5000 references.

### 4. Add CI (`.github/workflows/test.yml`)
Use the workflow in `docs/testing-strategy.md §5` verbatim. It runs `backend-v2` tests (excluding `integration`), guards `requirements.txt` encoding (closes the TD-001 watch item), and runs frontend tests `--if-present`.

## Constraints

- Verify `backend-v2` is fully self-contained before deleting `backend/` — `grep -rn "backend/" backend-v2/` should return nothing functional.
- This is a big delete: state in plain English what's being removed and confirm nothing in `backend-v2/` or `frontend/` imports from `backend/`.
- One commit for the delete, one for docs+CI, so the delete is easy to revert if something was missed.

## Verification Steps

1. `cd backend-v2 && pytest -m "not integration"` → still green after the delete.
2. `grep -rn "localhost:5000\|Flask\|backend/app" .` → only historical mentions in `docs/changelog.md` / study docs remain.
3. Push a branch → CI workflow runs and passes; the encoding-guard step executes.
4. Frontend still uploads and renders against port 8000.

## Commit Messages

```
chore(bsa-18): decommission Flask backend

- remove backend/ (Flask app, tests, conftest, requirements)
- remove backend-v2/tests/test_parity.py (nothing left to compare)
```
```
docs+ci(bsa-18): FastAPI-only docs; add GitHub Actions incl. TD-001 guard

- CLAUDE.md, architecture.md, requirements.md: drop dual-backend framing
- .github/workflows/test.yml: backend-v2 pytest + requirements UTF-8 guard
```

## After This Task

Write `docs/study/flask-decommission-bsa18.md` (what was removed, why now, the drift risk it closes). Mark TD-001 resolved in `docs/tech-debt.md`. Update `docs/changelog.md`.
