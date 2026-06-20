# Prompt: Remove Stale localhost:5000 Strings — TD-037

**Task:** Centralize the API base URL and fix two user-facing error messages that still reference the deprecated Flask port.
**Sprint ref:** Sprint-03 · Ticket: TD-037
**Review ref:** `docs/code-review.md` → CR-F2-01
**Estimated time:** 20 minutes

---

## Why This Change Is Needed

BSA-09 moved the app to FastAPI (port 8000), but three references to port 5000 remain in the frontend:
- `frontend/services/api.ts` line 3 — env fallback `?? 'http://localhost:5000'`
- `frontend/services/api.ts` line 22 — network error message text
- `frontend/App.tsx` line 35 — network error message text

A user whose backend is down is told to check port 5000 — the wrong, soon-to-be-deleted backend. The functional URL is correct (it reads `VITE_API_URL`); only the fallback and the message strings are stale.

## Files to Read First

1. `frontend/services/api.ts` — `API_BASE` definition and the thrown error strings
2. `frontend/App.tsx` — the `handleFileSelect` catch block
3. `frontend/.env.local` — confirms `VITE_API_URL=http://localhost:8000`

## Changes to Make

### 1. `api.ts` — default to 8000 and export the base

```typescript
// BEFORE
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:5000';

// AFTER
export const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
```

Update the line ~22 network error to interpolate the base:

```typescript
throw new Error(`Network Error: Unable to connect to the backend server. Please ensure the API is running at ${API_BASE}.`);
```

### 2. `App.tsx` — interpolate the base instead of hardcoding

```typescript
import { uploadBankStatement, API_BASE } from './services/api';
// ...
errorMessage = `Connection failed. Ensure backend is running at ${API_BASE}`;
```

## Constraints

- One source of truth for the URL — never hardcode a port string again.
- Don't touch the functional fetch logic; only the fallback default and the message text.

## Verification Steps

1. `grep -rn "5000" frontend/` → zero hits (excluding `.env.example` historical comments if intentional — check those too).
2. Stop the backend, upload a file → error message names port 8000.
3. `npm run build` → no TypeScript errors (the new `API_BASE` export resolves).

## Commit Message

```
fix(td-037): centralize API base URL; drop stale localhost:5000 strings

- api.ts: export API_BASE, default to :8000, interpolate into error text
- App.tsx: use API_BASE in connection-failed message
```

## After This Task

Update `docs/changelog.md`. Proceed to `03-summary-typing.md`.
