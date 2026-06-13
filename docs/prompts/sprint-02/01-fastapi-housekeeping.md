# Prompt: FastAPI Housekeeping — TD-028, TD-029, TD-030, TD-032

**Task:** Fix four 1-liner tech debt items in `backend-v2/` before writing any new code this sprint.  
**Sprint ref:** Sprint-02 · Tech debt IDs: TD-028, TD-029, TD-030, TD-032  
**Estimated time:** 30 minutes  
**Complexity:** Low — each fix is 1-5 lines

---

## Why This Change Is Needed

These four issues were found during the Sprint-01 code review (`docs/code-review.md`). They are all trivial to fix but carry real risk:

- **TD-028:** `reload=True` hardcoded in `backend-v2/run.py` — the exact same class of bug as `debug=True` in the original Flask `run.py` that we fixed in Sprint-01. In production this causes double-startup and exposes Uvicorn internals.
- **TD-029:** `import requests` is a dead import in `backend-v2/app/models/analyzer.py`. The only caller (`verify_bank_account_with_pennyless`) was deleted from the Flask side but the import was never removed from the FastAPI copy. Unused deps are noise and attack surface.
- **TD-030:** CORS has `allow_credentials=True` with `allow_methods=["*"]` — the CORS spec forbids wildcards when credentials are enabled. This will silently break when auth is added.
- **TD-032:** `UPLOAD_DIR = Path("uploads")` resolves relative to wherever `uvicorn` is launched, not relative to `backend-v2/`. Launch from the wrong directory and uploads go to the wrong place with no error.

---

## Files to Read First

Before making any changes, read these files to understand the current state:

1. `backend-v2/run.py`
2. `backend-v2/app/models/analyzer.py` (just the first 15 lines — the imports)
3. `backend-v2/app/main.py`
4. `backend-v2/app/routers/analyze.py` (first 20 lines — the UPLOAD_DIR and imports)
5. `backend-v2/requirements.txt`

---

## Changes to Make

### Fix 1: TD-028 — `backend-v2/run.py`

**Current code:**
```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
```

**Change to:**
```python
import os
import uvicorn

if __name__ == "__main__":
    reload = os.getenv("UVICORN_RELOAD", "false").lower() == "true"
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=reload)
```

---

### Fix 2: TD-029 — `backend-v2/app/models/analyzer.py`

Find and remove the line:
```python
import requests
```

This is a dead import — `requests` is used nowhere in this file. Confirm by searching for `requests.` (with a dot) — there should be zero matches.

Also remove from `backend-v2/requirements.txt`:
```
requests==2.32.5
```

---

### Fix 3: TD-030 — `backend-v2/app/main.py`

**Current CORS setup:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Change to:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
```

---

### Fix 4: TD-032 — `backend-v2/app/routers/analyze.py`

**Current code (near the top of the file):**
```python
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
```

**Change to:**
```python
UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
```

Explanation: `Path(__file__)` is the absolute path to `analyze.py`. Going up three parents: `routers/` → `app/` → `backend-v2/` → the `uploads/` folder inside `backend-v2/`. This works regardless of where uvicorn is launched from.

---

## Constraints

- Make each fix as a separate edit (one change per file), not a combined rewrite
- Explain the fix in plain English before each edit
- Do not change anything else in these files
- Do not rename variables or restructure code
- After all four fixes, run `cd backend-v2 && python -m pytest tests/ -v` if tests already exist, otherwise just confirm the app starts with `python run.py`

---

## Verification Steps

1. `grep -n "reload=True" backend-v2/run.py` → should return nothing
2. `grep -n "import requests" backend-v2/app/models/analyzer.py` → should return nothing
3. `grep -n "requests" backend-v2/requirements.txt` → should return nothing
4. `grep -n "allow_methods" backend-v2/app/main.py` → should show the explicit list
5. `grep -n "UPLOAD_DIR" backend-v2/app/routers/analyze.py` → should show `Path(__file__)`

---

## Commit Message (do not run — hand to Ronit)

```
fix(backend-v2): housekeeping — env-reload, dead requests import, CORS wildcards, UPLOAD_DIR path

TD-028: reload=True → UVICORN_RELOAD env var (mirrors Flask debug fix)
TD-029: remove dead `import requests` + requests dep (Pennyless fn was deleted, import wasn't)
TD-030: CORS allow_methods/headers → explicit lists (wildcard + credentials violates spec)
TD-032: UPLOAD_DIR = Path(__file__).parent anchored to file, not cwd

All four are 1-liners. No logic changes.
```

---

## After This Task

Update `docs/changelog.md` with an entry for each fix. Then move to `docs/prompts/sprint-02/02-fastapi-tests.md`.
