# Prompt: Flask → FastAPI Cutover — BSA-09

**Task:** Point the frontend at FastAPI (port 8000), update all docs/config, and deprecate the Flask backend.  
**Sprint ref:** Sprint-02 · Ticket: BSA-09  
**Estimated time:** 1 hour  
**Prerequisite:** BSA-10 tests must pass before this prompt is run.

---

## Why This Change Is Needed

The FastAPI backend has been running on port 8000 since BSA-02/03, but the frontend still points at Flask (port 5000). All the work done in Sprint-01 (FastAPI scaffold, analyze endpoint, async parsing, Pydantic schemas, Swagger UI) is invisible to users until this cutover happens. More importantly: BSA-04 (LLM categorization) depends on FastAPI's async architecture — it cannot be added to Flask.

This is the "collect on the investment" task.

---

## Files to Read First

1. `frontend/.env.example` — see what env vars the frontend exposes
2. `frontend/src/services/api.ts` (or `frontend/services/api.ts`) — confirm `VITE_API_URL` usage
3. `backend-v2/app/main.py` — confirm FastAPI runs on port 8000
4. `CLAUDE.md` — check for port references to update
5. `docs/architecture.md` — we'll update this to reflect the new state

---

## Changes to Make

### 1. `frontend/.env` or `frontend/.env.local`

Create (or update) the local env file:
```env
VITE_API_URL=http://localhost:8000
```

If `.env.local` doesn't exist, create it. This file is in `.gitignore` (local-only config). Do not commit it.

### 2. `frontend/.env.example`

Update the example to show the FastAPI port:
```env
# Backend API base URL
# Sprint-01: Flask runs on port 5000
# Sprint-02+: FastAPI runs on port 8000
VITE_API_URL=http://localhost:8000
```

### 3. `backend/run.py` — Add deprecation notice

Add a startup warning to the Flask backend so it's clear it's being retired:

```python
# Add near the top, before app.run():
import warnings
warnings.warn(
    "Flask backend (port 5000) is deprecated as of Sprint-02. "
    "Use FastAPI backend (port 8000) via backend-v2/run.py. "
    "Flask will be removed in Sprint-03.",
    DeprecationWarning,
    stacklevel=2,
)
```

Do not delete the Flask backend yet — keep it alive for one sprint as a rollback option.

### 4. `CLAUDE.md` — Update port references

Search `CLAUDE.md` for any mentions of `port 5000` or `localhost:5000` and update them to reference both:
- Flask (legacy): port 5000 — to be removed Sprint-03
- FastAPI (active): port 8000

### 5. `docs/architecture.md` — Mark Flask as deprecated

Add a section or note:
```markdown
## Backend Status (as of Sprint-02)

| Backend | Port | Status |
|---------|------|--------|
| FastAPI (`backend-v2/`) | 8000 | ✅ Active — all new development here |
| Flask (`backend/`) | 5000 | ⚠️ Deprecated — removal scheduled Sprint-03 |
```

---

## Constraints

- Do not delete any Flask files — only deprecate them
- Do not change the FastAPI code itself — this is a config/docs change only
- Do not commit `.env.local` (it should be in `.gitignore`)
- If the frontend uses a hardcoded `localhost:5000` anywhere (not via `VITE_API_URL`), flag it but do not fix it without a separate prompt

---

## Verification Steps

1. Start FastAPI: `cd backend-v2 && python run.py`
2. Start frontend: `cd frontend && npm run dev`
3. Upload a test CSV from the UI — confirm the request goes to `localhost:8000` (check browser network tab)
4. Confirm `/docs` (Swagger UI) is accessible at `http://localhost:8000/docs`
5. Stop FastAPI, confirm the frontend shows an error (not silently falling back to Flask)
6. `grep -rn "localhost:5000" frontend/src/` → should return nothing

---

## Commit Message (hand to Ronit)

```
feat(bsa-09): cut frontend over to FastAPI on port 8000; deprecate Flask

- frontend/.env.example: VITE_API_URL now points to port 8000
- backend/run.py: DeprecationWarning added — Flask scheduled for removal Sprint-03
- CLAUDE.md: updated port references
- docs/architecture.md: backend status table (FastAPI active, Flask deprecated)

Flask code is preserved for one sprint as a rollback option.
Frontend now talks exclusively to FastAPI.
```

---

## After This Task

Update `docs/changelog.md`. This is the inflection point — all new backend work from here goes in `backend-v2/` only. Proceed to `docs/prompts/sprint-02/04-llm-categorization.md`.
