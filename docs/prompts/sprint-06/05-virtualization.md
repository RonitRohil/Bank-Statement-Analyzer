# Sprint-06 Prompt 05 — TD-018: TransactionTable Client-Side Pagination

## Task: Add client-side pagination to TransactionTable (P1 — do only if capacity allows after P0)

**Context:** `TransactionTable.tsx` currently renders all rows at once. With BSA-20 (history reload) and multi-statement workflows, row counts can reach 1,000+. Client-side pagination is the safe, low-dependency approach for Sprint-06. Proper virtualization (`@tanstack/react-virtual`) is deferred to Sprint-07 if needed.

**Files to read first:**

- `frontend/components/TransactionTable.tsx`
- `frontend/types.ts`

---

## Change: Add pagination to `TransactionTable.tsx`

**Approach:** Add `currentPage` state, slice the transactions array for rendering, show a pager at the bottom.

**Constants to add at the top of the component:**

```tsx
const PAGE_SIZE = 50;
```

**State to add:**

```tsx
const [currentPage, setCurrentPage] = useState(1);
```

**Reset page when transactions prop changes** (so switching to a different statement starts at page 1):

```tsx
useEffect(() => {
  setCurrentPage(1);
}, [transactions]);
```

**Slice for rendering:**

```tsx
const totalPages = Math.ceil(transactions.length / PAGE_SIZE);
const pageTransactions = transactions.slice(
  (currentPage - 1) * PAGE_SIZE,
  currentPage * PAGE_SIZE,
);
```

Use `pageTransactions` in the `<tbody>` map instead of `transactions`.

**Pager UI** — add below the `</table>` closing tag:

```tsx
{
  totalPages > 1 && (
    <div className="flex items-center justify-between mt-3 text-sm text-slate-500">
      <span>
        Showing {(currentPage - 1) * PAGE_SIZE + 1}–
        {Math.min(currentPage * PAGE_SIZE, transactions.length)} of{" "}
        {transactions.length}
      </span>
      <div className="flex gap-2">
        <button
          onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
          disabled={currentPage === 1}
          className="px-3 py-1 rounded border border-slate-200 disabled:opacity-40 hover:bg-slate-50"
        >
          ← Prev
        </button>
        <span className="px-3 py-1">
          {currentPage} / {totalPages}
        </span>
        <button
          onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
          disabled={currentPage === totalPages}
          className="px-3 py-1 rounded border border-slate-200 disabled:opacity-40 hover:bg-slate-50"
        >
          Next →
        </button>
      </div>
    </div>
  );
}
```

**Constraints:**

- Do not change the table column structure.
- Do not change the search/filter logic — search still filters the full `transactions` array. Apply pagination _after_ filtering.
- If there's a search filter active, reset to page 1 when the search term changes.
- No new npm dependencies.
- Keep the export buttons (`↓ CSV`, `↓ Excel`) exporting all transactions (not just the current page).

## Verification

Manual: upload a statement with 100+ transactions. Verify:

- Page 1 shows rows 1–50.
- "Next →" shows rows 51–100.
- Search filters work and reset to page 1.
- Export buttons still export all rows.

No backend changes. No new tests needed (UI-only change).

## Changelog entry required

Add to `docs/changelog.md`.
