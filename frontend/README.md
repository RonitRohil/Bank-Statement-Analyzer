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
                              SummaryResponse, RecurringCandidate
services/api.ts            ← uploadBankStatement(), getSummary(), exportTransactions()
index.html                 ← Vite entry
components/
  FileUpload.tsx            ← drag-drop + click; loading state; error alerts
  AccountOverview.tsx       ← bank details, account holder, confidence %, statement period
  AnalyticsCharts.tsx       ← balance history (line), income/expense (bar), merchants (pie)
  SpendingSummary.tsx       ← income/expense/net tiles + top-5 categories + top-5 merchants (BSA-12)
  InsightsStrip.tsx         ← pill-style smart insight callouts (BSA-15)
  MerchantInsights.tsx      ← merchant table: count, avg/median amount, common days;
                              ↻ green pill on recurring candidates (BSA-07 lite)
  TransactionTable.tsx      ← transaction list; indigo "AI" badge on LLM-enriched rows;
                              "↓ CSV" + "↓ Excel" export buttons in table header (BSA-13)
  ErrorBoundary.tsx         ← per-section error boundary
```

No global state manager — all data flows top-down via props from `App.tsx`.

## Backend

Targets the **FastAPI backend on port 8000** via `VITE_API_URL`.

| Function | Endpoint | Purpose |
|----------|----------|---------|
| `uploadBankStatement(file)` | `POST /api/analyze/bank/statement` | Upload and parse a statement |
| `getSummary(transactions)` | `POST /api/analyze/bank/summary` | Compute financial summary |
| `exportTransactions(transactions, format)` | `POST /api/export/transactions` | Download CSV or Excel |

`exportTransactions()` POSTs the transactions array, receives a blob, creates an object URL, triggers the browser download dialog, and revokes the URL — no server-side temp files.

## Key Types (`types.ts`)

```typescript
Transaction          // date, type, amount, narration, method, merchant, category[], llm_enriched
AnalysisResult       // transactions[], account_info, confidence_summary, merchant_insights,
                     // insights: string[], recurring_candidates: RecurringCandidate[]
RecurringCandidate   // merchant, count, avg_amount, std_amount, cv, first_seen, last_seen
SummaryResponse      // income, expenses, net, by_category[], top_merchants[], currency
```

## Open Issues

- **TD-018:** `TransactionTable` renders every row (no virtualization). Priority rises now that persistence can accumulate hundreds of rows across multiple statements. Add `@tanstack/react-virtual` or pagination before Sprint-05's history view lands.
- **No frontend tests.** The CI frontend step is a no-op. `SpendingSummary`, `InsightsStrip`, and `MerchantInsights` have no test coverage.

See `../docs/tech-debt.md` for the full list.

---

*Backend: `../backend/README.md` · Tech debt: `../docs/tech-debt.md` · AI workflow: `../CLAUDE.md`*
