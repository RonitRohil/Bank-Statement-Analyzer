# Prompt 01 — Sprint-04 Housekeeping

## Task: Schema fixes, AI badge, backend rename (TD-039 / TD-040 / TD-041 / TD-038)

**Context:** Four small items that should be the first commit of Sprint-04. All are < 30 min each. None require new features — just closing gaps found during the Sprint-03 code review. Do them all in one patch.

**Files to read first:**

- `backend/app/models/schemas.py`
- `frontend/components/TransactionTable.tsx`
- `frontend/types.ts`

---

## Change 1 — TD-039: Add `insights` field to `AnalysisResult` schema

**File:** `backend/app/models/schemas.py`

Find the `AnalysisResult` Pydantic model. Add:

```python
insights: list[str] = []
```

This field is already emitted by `analyze.py` (injected into the dict after `generate_insights()`) and consumed by the frontend. The Pydantic model was never updated, causing Swagger UI to omit it and future `response_model` enforcement to strip it silently.

**Constraints:**

- Default to `[]` so existing tests don't break
- Do not change the field name or type

**Verification:** Run `pytest`. Check Swagger UI at `/docs` — `AnalysisResult` should now list `insights`.

---

## Change 2 — TD-040: Add `currency` field to `SummaryResponse`

**File:** `backend/app/models/schemas.py`

Find the `SummaryResponse` Pydantic model. Add:

```python
currency: str = "INR"
```

The frontend reads `summary.currency ?? "INR"` as a fallback. The backend not emitting this field creates an implicit contract. Make it explicit. INR is the correct default for a single-market tool.

**Constraints:**

- Default `"INR"`, not `None`
- Do not change the summary endpoint math

**Verification:** `curl POST /api/analyze/bank/summary` with a sample payload — response should include `"currency": "INR"`.

---

## Change 3 — TD-041: Complete `backend-v2/` → `backend/` rename

Run these commands in the project root on your local machine (not in Claude Code — the sandbox can't do the git rename):

```bash
# In your terminal, from the project root:
rmdir backend          # remove the empty placeholder directory
git mv backend-v2 backend
git commit -m "BSA-20: rename backend-v2 to backend (TD-041)"
```

After committing, verify:

```bash
grep -rn "backend-v2" . --include="*.md" --include="*.yml" --include="*.py" --include="*.ts" --include="*.tsx" | grep -v ".git"
```

Should return zero matches (historical prompt files like `docs/prompts/sprint-02/` are OK — they are past-tense documents).

**Note for Claude Code:** If you are running after the user has done the git rename, update any remaining `backend-v2` references you find in live files (non-historical docs). If the rename has not been done yet, skip this step and note it in the changelog.

---

## Change 4 — TD-038 (remainder): AI badge on enriched rows in TransactionTable

**Files:**

- `frontend/components/TransactionTable.tsx`
- `frontend/types.ts` (already has `llm_enriched?: boolean` on `Transaction`)

In `TransactionTable.tsx`, find where the category column renders. Add a small "AI" indicator (badge/pill/icon) next to the category when `txn.llm_enriched === true`.

Suggested implementation (keep it subtle — this is metadata, not the primary content):

```tsx
{
  txn.category && txn.category.length > 0 ? (
    <span className="flex items-center gap-1">
      <span>{txn.category.join(", ")}</span>
      {txn.llm_enriched && (
        <span
          title="AI-categorized"
          className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-semibold bg-indigo-100 text-indigo-700"
        >
          AI
        </span>
      )}
    </span>
  ) : (
    <span className="text-slate-400 text-xs">—</span>
  );
}
```

**Constraints:**

- The badge must be `title="AI-categorized"` for accessibility
- Do not change the column layout or other row rendering
- If `llm_enriched` is undefined/false, render exactly as today

**Verification:** Upload a statement with uncategorized narrations while Ollama is running. Enriched rows should show the "AI" badge in the category cell.

---

## Documentation

After all four changes:

1. Add an entry to `docs/changelog.md`:
   - Type: Bug fix / cleanup
   - Items closed: TD-039, TD-040, TD-041, TD-038 (partial → full)
   - Files affected: list them

2. Update `docs/tech-debt.md`: mark TD-039, TD-040, TD-041, TD-038 as ✅ resolved.

**Verification (all):** `pytest` from `backend/` — all tests green.
