# Prompt: Spending Summary Card + AI Badge (frontend) — BSA-12 / TD-038

**Task:** Surface the two Sprint-02 features in the UI — call `/api/analyze/bank/summary` and render a summary card; add an "AI-categorized" badge on `llm_enriched` rows.
**Sprint ref:** Sprint-03 · Tickets: BSA-12, TD-038
**Review ref:** `docs/code-review.md` → CR-F2-02, CR-F2-06, CR-S2-11
**Estimated time:** 3–4 hours · **Depends on:** `03-summary-typing.md`

---

## Why This Change Is Needed

BSA-04 and BSA-05 shipped backend-only. The summary endpoint returns income/expense/net/top-categories that nothing renders, and `llm_enriched` isn't even in the TS types. This prompt makes the value visible — the single highest-value frontend work available.

## Files to Read First

1. `frontend/types.ts` — add `llm_enriched` to `Transaction`; add summary types
2. `frontend/services/api.ts` — add a `getSummary()` call (reuse `API_BASE`)
3. `frontend/App.tsx` — where the dashboard is composed
4. `frontend/components/AnalyticsCharts.tsx` — currently recomputes income/expense client-side (CR-F2-04); the summary endpoint is the source of truth
5. `backend-v2/app/models/schemas.py` — `SummaryResponse` shape to mirror in TS

## Changes to Make

### 1. Types (`types.ts`)
- Add `llm_enriched?: boolean` to `Transaction`.
- Add `SummaryResponse`, `CategoryBreakdown`, `TopMerchant` interfaces mirroring the Pydantic models.
- Also fix CR-F2-07 while here: type `amount`/`balance` as `number | null` to match the backend.

### 2. API (`api.ts`)
```typescript
export const getSummary = async (transactions: Transaction[]): Promise<SummaryResponse> => {
  const res = await fetch(`${API_BASE}/api/analyze/bank/summary`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ transactions }),
  });
  if (!res.ok) throw new Error(`Summary failed: ${res.status}`);
  return res.json();
};
```

### 3. New component `components/SpendingSummary.tsx`
- Props: `transactions: Transaction[]`.
- On mount (or when transactions change), call `getSummary`. Show income / expense / net big-number tiles, a top-categories list, and a top-merchants list.
- Render the >100% caveat honestly — label category percentages as "share of spend," not a 100% pie. (See CR-S2-06.)
- Wrap in the existing `ErrorBoundary` pattern; show a graceful fallback if the call fails.

### 4. Wire into `App.tsx`
Add `<SpendingSummary transactions={data.transactions} />` near the top of the dashboard, above or beside `AnalyticsCharts`.

### 5. AI badge
In `TransactionTable.tsx`, when `txn.llm_enriched`, render a small "AI" pill next to the category/method so users can see which categories came from the model.

## Constraints

- Reuse `API_BASE` (from prompt 02) — no new hardcoded URLs.
- Prefer the summary endpoint's numbers over client-side recomputation in `AnalyticsCharts` where they overlap (kills the two-sources-of-truth drift, CR-F2-04/S2-11).
- Match the existing Tailwind visual language (cards: `bg-white rounded-xl shadow-sm border border-slate-100`).
- Keep it a controlled, prop-driven component — no global state.

## Verification Steps

1. **Vitest** `SpendingSummary.test.tsx`: mock `getSummary`, assert tiles render the right numbers; assert graceful fallback on rejection.
2. Manual: upload a statement → summary card shows totals matching the transaction table; enriched rows show the AI badge.
3. `npm run build` → no TS errors.

## Commit Message

```
feat(bsa-12,td-038): spending summary card + AI-categorized badge

- types.ts: SummaryResponse types; llm_enriched on Transaction; nullable amount/balance
- api.ts: getSummary() against /api/analyze/bank/summary
- components/SpendingSummary.tsx: income/expense/net + top categories/merchants
- TransactionTable.tsx: AI pill on llm_enriched rows
- App.tsx: render SpendingSummary in dashboard
```

## After This Task

Write `docs/study/spending-summary-bsa12.md`. Update `docs/changelog.md` and mark TD-038 resolved in `docs/tech-debt.md`.
