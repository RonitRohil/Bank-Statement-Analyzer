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
types.ts                   ← AccountInfo, Transaction, AnalysisResult, ApiResponse, SummaryResponse
services/api.ts            ← uploadBankStatement(), getSummary() — POST to ${VITE_API_URL}
index.html                 ← Vite entry
components/
  FileUpload.tsx            ← drag-drop + click; loading state; error alerts
  AccountOverview.tsx       ← bank details, account holder, confidence %, statement period
  AnalyticsCharts.tsx       ← balance history (line), income/expense (bar), merchants (pie)
  SpendingSummary.tsx       ← income/expense/net tiles + top-5 categories + top-5 merchants (BSA-12)
  InsightsStrip.tsx         ← pill-style smart insight callouts (BSA-15)
  MerchantInsights.tsx      ← merchant table: count, avg/median amount, common days
  TransactionTable.tsx      ← transaction list with AI badge on LLM-enriched rows
  ErrorBoundary.tsx         ← per-section error boundary
```

No global state manager — all data flows top-down via props from `App.tsx`.

## Backend

Targets the **FastAPI backend on port 8000** via `VITE_API_URL`.

- `uploadBankStatement(file)` → `POST /api/analyze/bank/statement`
- `getSummary(transactions)` → `POST /api/analyze/bank/summary`

## Open Issues

- **TD-018:** `TransactionTable` renders every row (no virtualization). Add pagination before large multi-statement data arrives (Sprint-04+).
- **No frontend tests.** The CI frontend step is a no-op. `SpendingSummary` and `InsightsStrip` have no test coverage.

See `../docs/tech-debt.md` for the full list.
