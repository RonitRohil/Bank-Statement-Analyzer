# Frontend — Bank Statement Analyzer

React 19 + TypeScript + Vite dashboard for uploading and visualizing bank statements.

## Stack

- **React 19** with TypeScript
- **Vite 6** (dev server on port 3000)
- **Recharts 3** — balance history (line), income/expense (bar), merchant pie chart
- **Lucide React** — icons
- **Tailwind CSS** (CDN)

## Setup

```bash
npm install

# Create .env.local
echo "VITE_API_URL=http://localhost:8000" > .env.local

npm run dev      # http://localhost:3000
npm run build    # outputs to dist/
npm run preview  # preview production build
```

## Structure

Components live at the project root (no `src/` directory):

```
App.tsx                    ← root; manages analysis state, layout
types.ts                   ← AccountInfo, Transaction, AnalysisResult, ApiResponse,
                              SummaryResponse, RecurringCandidate, MonthSummary,
                              ComparisonResponse, ConfirmedRecurringItem
services/api.ts            ← uploadBankStatement(), getSummary(), exportTransactions(),
                              getMonthlyComparison(), getRecurringMerchants(), getStatements()
index.html                 ← Vite entry
components/
  FileUpload.tsx            ← drag-drop + click; loading state; error alerts
  AccountOverview.tsx       ← bank details, account holder, confidence %, statement period
  AnalyticsCharts.tsx       ← balance history (line), income/expense (bar), merchants (pie)
  SpendingSummary.tsx       ← income/expense/net tiles + top-5 categories + top-5 merchants (BSA-12)
  InsightsStrip.tsx         ← pill-style smart insight callouts (BSA-15)
  MerchantInsights.tsx      ← merchant table: count, avg/median amount, common days;
                              ↻ green pill on recurring candidates (BSA-07 lite)
  MonthlyComparison.tsx     ← Recharts ComposedChart: income/expense bars + net trend line (BSA-17, Sprint-05)
  SubscriptionsCard.tsx     ← confirmed cross-statement recurring merchants + monthly cost (BSA-07-full, Sprint-05)
  TransactionTable.tsx      ← transaction list; indigo "AI" badge on LLM-enriched rows;
                              "↓ CSV" + "↓ Excel" export buttons in table header (BSA-13)
  ErrorBoundary.tsx         ← per-section error boundary
```

No global state manager — all data flows top-down via props from `App.tsx`.

## Backend

Targets the **FastAPI backend on port 8000** via `VITE_API_URL`.

| Function                                   | Endpoint                           | Purpose                                                             |
| ------------------------------------------ | ---------------------------------- | ------------------------------------------------------------------- |
| `uploadBankStatement(file, persist?)`      | `POST /api/analyze/bank/statement` | Upload and parse a statement; `persist=true` stores to SQLite       |
| `getSummary(transactions)`                 | `POST /api/analyze/bank/summary`   | Compute income/expense/net + category breakdown                     |
| `exportTransactions(transactions, format)` | `POST /api/export/transactions`    | Download CSV or Excel                                               |
| `getMonthlyComparison(accountNumber)`      | `GET /api/statements/compare`      | Month-over-month income/expense/delta for MonthlyComparison chart   |
| `getRecurringMerchants(accountNumber)`     | `GET /api/statements/recurring`    | Cross-statement confirmed recurring merchants for SubscriptionsCard |
| `getStatements()`                          | `GET /api/statements`              | List all persisted statements                                       |

`exportTransactions()` POSTs the transactions array, receives a blob, creates an object URL, triggers the browser download dialog, and revokes the URL — no server-side temp files.

## Key Types (`types.ts`)

```typescript
Transaction; // date, type, amount, narration, method, merchant, category[], llm_enriched
AnalysisResult; // transactions[], account_info, confidence_summary, merchant_insights,
// insights: string[], recurring_candidates: RecurringCandidate[]
RecurringCandidate; // merchant, count, avg_amount, std_amount, cv, first_seen, last_seen
SummaryResponse; // income, expenses, net, by_category[], top_merchants[], currency
MonthSummary; // month (YYYY-MM), income, expenses, net, top_category, delta_expenses_pct
ComparisonResponse; // account_number, months: MonthSummary[]
ConfirmedRecurringItem; // merchant, confirmed_months[], avg_amount, estimated_monthly_cost
```

## Open Issues

- **TD-018 (Sprint-06 P1):** `TransactionTable` renders every row — no pagination or virtualization. Planned for Sprint-06 as client-side pagination (PAGE_SIZE=50, Prev/Next pager). See `docs/prompts/sprint-06/05-virtualization.md`.
- **No frontend tests.** The CI frontend step is a no-op. `SpendingSummary`, `InsightsStrip`, `MonthlyComparison`, and `SubscriptionsCard` have no test coverage.

See `../docs/tech-debt.md` for the full list.

---

_Backend: `../backend/README.md` · Tech debt: `../docs/tech-debt.md` · AI workflow: `../CLAUDE.md`_
