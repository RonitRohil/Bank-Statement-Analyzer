# Sprint-06 Prompt 03 — BSA-20: Statement History UI

## Task: Add DELETE endpoint and HistoryPanel frontend component

**Context:** `GET /api/statements` already exists (Sprint-04) with pagination (Sprint-05). This ticket adds the DELETE endpoint and the frontend history panel so users can browse, reload, and delete their past uploads.

**Files to read first:**

- `backend/app/routers/statements.py`
- `backend/app/db/models.py`
- `backend/app/db/crud.py`
- `backend/app/main.py`
- `frontend/App.tsx`
- `frontend/services/api.ts`
- `frontend/types.ts`

---

## Backend: Add `DELETE /api/statements/{id}` to `statements.py`

Add this endpoint to `backend/app/routers/statements.py`.

**Important:** Delete `TransactionDB` rows BEFORE `StatementDB` row. SQLite FK enforcement is off by default — orphan rows are a real risk if the delete order is wrong.

```python
@router.delete("/api/statements/{statement_id}", status_code=204)
def delete_statement(
    statement_id: int,
    session: Session = Depends(get_session),
):
    """Delete a stored statement and all its associated transactions."""
    stmt = session.get(StatementDB, statement_id)
    if not stmt:
        raise HTTPException(status_code=404, detail=f"Statement {statement_id} not found")

    # Delete child rows first (FK safety — SQLite doesn't enforce FKs by default)
    txns = session.exec(
        select(TransactionDB).where(TransactionDB.statement_id == statement_id)
    ).all()
    for txn in txns:
        session.delete(txn)

    session.delete(stmt)
    session.commit()
    # 204 No Content — no return value
```

**Constraints:**

- Return 204 (no body) on success. FastAPI handles this with `status_code=204`.
- Return 404 if the statement ID doesn't exist.
- Never delete transactions from a different statement.

---

## Frontend: `frontend/components/HistoryPanel.tsx` (new file)

A collapsible panel listing all stored statements. Each row has a "Load" and "Delete" action.

**Component interface:**

```tsx
interface StoredStatement {
  id: number;
  bank_name: string | null;
  account_holder: string | null;
  account_number: string | null;
  period_from: string | null;
  period_to: string | null;
  uploaded_at: string;
  confidence_overall: number | null;
}

interface Props {
  statements: StoredStatement[];
  onLoad: (id: number) => void; // parent fetches transactions and updates dashboard
  onDelete: (id: number) => void; // parent removes entry from list
  loading: boolean;
}
```

**Behavior:**

- Renders a card with heading "Statement History" and a count badge (e.g. "3 statements").
- If empty: show a soft empty state — "No statements stored yet. Upload with 'Save to history' to build your archive."
- Each row shows: bank name (or "Unknown Bank"), account holder, period range, upload date, confidence score as a percentage.
- "Load" button: calls `onLoad(id)`. While loading, show a spinner on the row.
- "Delete" button: shows a red trash icon. On click, show an inline confirmation ("Delete this statement? This cannot be undone.") with Confirm/Cancel. On confirm, call `onDelete(id)`.
- Paginate: show 10 at a time, "Show more" button loads the next 10 from the already-fetched list (client-side slice, not a new API call).

---

## Frontend: `frontend/services/api.ts`

Add two functions:

```typescript
export async function deleteStatement(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/statements/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
}

export async function getStatementTransactions(id: number) {
  const res = await fetch(
    `${API_BASE}/api/statements/${id}/transactions?limit=500`,
  );
  if (!res.ok) throw new Error(`Failed to load transactions: ${res.status}`);
  return res.json() as Promise<{
    statement_id: number;
    transactions: Transaction[];
  }>;
}
```

Import `Transaction` from the appropriate types file.

---

## Frontend: `frontend/App.tsx` — wire up `HistoryPanel`

**In `App.tsx`:**

1. Add state: `const [storedStatements, setStoredStatements] = useState<StoredStatement[]>([])`.
2. Fetch statements on mount (after page load, if any persist): call `GET /api/statements?limit=50` and set state.
3. After a successful persist upload, re-fetch the statements list to include the new entry.
4. Handle `onLoad(id)`: call `getStatementTransactions(id)`, then update the main `data` state with the loaded transactions (same shape as an analyze response — set `data.result.transactions`).
5. Handle `onDelete(id)`: call `deleteStatement(id)`, then remove the entry from `storedStatements` state.
6. Render `<HistoryPanel>` below `QAChat` (or below `SubscriptionsCard` if BSA-06 isn't shipped yet). Only render when `storedStatements.length > 0`.

**Constraints:**

- Do not break the existing stateless flow. `HistoryPanel` is purely additive.
- Loading a statement from history should populate the same `data` state that `FileUpload` populates — same charts, same table, same account overview.
- Keep the "onLoad" transaction shape compatible with the existing `AnalysisResult` type.

---

## Tests: `backend/tests/test_persistence.py` — extend existing file

Add 2 new tests to the existing `test_persistence.py` (do not create a new file):

| Test                               | What it checks                                                                                       |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `test_delete_statement`            | Save a statement → DELETE `/api/statements/{id}` → 204 → GET `/api/statements` no longer includes it |
| `test_delete_removes_transactions` | Save a statement with transactions → DELETE → GET `/api/statements/{id}/transactions` → 404          |

Use the same in-memory SQLite fixture pattern as the existing tests in that file.

---

## Constraints

- Do not modify existing endpoints.
- Do not modify existing tests.
- The `HistoryPanel` delete confirmation must be inline (no browser `confirm()` dialog).
- Match the existing Tailwind CSS style of other components (rounded-xl shadow-sm border border-slate-100 p-6).

## Verification

```bash
cd backend && pytest tests/test_persistence.py -v
pytest --tb=short -q
```

Manual: upload 2 statements with persist, open HistoryPanel, delete one — confirm it's gone from DB and UI.

## Changelog entry required

Add to `docs/changelog.md`.
