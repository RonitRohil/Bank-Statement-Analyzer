# Sprint-06 Prompt 01 — Housekeeping (CR-S5-01, CR-S5-04, CR-S5-05)

## Task: Three quick CR-S5 fixes — first commit of Sprint-06

**Context:** Sprint-05 code review found three low-effort items. Per CLAUDE.md convention, these are the first commit of the sprint. Ship them together before any new features.

**Files to read first:**

- `backend/app/routers/statements.py`
- `backend/app/db/crud.py`

---

## Change 1: CR-S5-05 — Add `.limit(5000)` cap in `get_monthly_summary()`

**File:** `backend/app/db/crud.py`

**Problem:** The inner query in `get_monthly_summary()` loads all `TransactionDB` rows for each statement with no cap. A statement with 2,000 rows × 12 statements = 24,000 objects loaded into memory per comparison call. As BSA-20 history UI encourages more uploads, this becomes a latent memory risk.

**Change to make:**

In `get_monthly_summary()`, find the inner transaction query (currently in the `for stmt in statements:` loop):

```python
txns = session.exec(
    select(TransactionDB).where(TransactionDB.statement_id == stmt.id)
).all()
```

Change it to:

```python
txns = session.exec(
    select(TransactionDB)
    .where(TransactionDB.statement_id == stmt.id)
    .limit(5000)  # cap: prevents memory spike on very large statements
).all()
```

**Constraints:**

- Only add `.limit(5000)`. Do not restructure the function.
- Keep the `.all()` call.

---

## Change 2: CR-S5-01 — Route ordering comment in `statements.py`

**File:** `backend/app/routers/statements.py`

**Problem:** `GET /api/statements/compare` and `GET /api/statements/recurring` must appear before `GET /api/statements/{statement_id}/transactions` in the router file. FastAPI matches first-wins; a future developer adding a new named route below `/{statement_id}` would cause 422 with no obvious error. No comment warns them.

**Change to make:**

Find the line that starts the parametric route (the one with `statement_id: int`). Add this comment on the line immediately before it:

```python
# NOTE: Named routes (/compare, /recurring) MUST appear above this parametric route.
# FastAPI matches first-wins — "compare" would be cast to int and return 422 if below.
```

Do not move any code. Just add the two-line comment.

---

## Change 3: CR-S5-04 — Staleness comment on `recurring_candidates_json` in `crud.py`

**File:** `backend/app/db/crud.py`

**Problem:** `recurring_candidates_json` stores BSA-07 lite output frozen at upload time. If the CV threshold in `detect_recurring()` is tuned later, existing rows won't update. No comment explains this design decision — a developer might try to "refresh" the column on threshold change.

**Change to make:**

In `save_statement()`, find the line that sets `recurring_candidates_json`:

```python
recurring_candidates_json=json.dumps(recurring_candidates or []),
```

Add a comment on the line above it:

```python
# Frozen at upload time. Re-upload the statement to refresh recurring detection.
# This is intentional: stores the detection result as it was at upload, independent of future threshold changes.
recurring_candidates_json=json.dumps(recurring_candidates or []),
```

---

## Verification

After all three changes:

```bash
cd backend
pytest --tb=short -q
```

All existing tests must pass (currently ~46). No new tests needed for these three changes — they are comments and a defensive limit, not new behavior.

**Expected output:** `46 passed` (or similar count, no failures).

## Changelog entry required

Add to `docs/changelog.md`:

```markdown
## 2026-06-22 — Sprint-06 housekeeping: CR-S5-01, CR-S5-04, CR-S5-05

**Type:** Cleanup (first commit of Sprint-06)
**Items closed:** CR-S5-05, CR-S5-01, CR-S5-04

- **CR-S5-05:** Added `.limit(5000)` to inner transaction query in `get_monthly_summary()` — prevents unbounded memory load as statement archive grows.
- **CR-S5-01:** Added route ordering comment above `/{statement_id}` in `statements.py` — warns future developers not to add named routes below the parametric route.
- **CR-S5-04:** Added staleness comment on `recurring_candidates_json` assignment in `save_statement()` — documents the frozen-at-upload-time design intent.

**Files affected:**

- `backend/app/db/crud.py`
- `backend/app/routers/statements.py`
```
