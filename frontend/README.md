# Frontend — Bank Statement Analyzer

React 19 + TypeScript + Vite dashboard for uploading and visualizing bank statements.

## Stack

- **React 19** with TypeScript
- **Vite 6** (dev server on port 3000)
- **Recharts 3** — balance history, income/expense bar, merchant pie chart
- **Lucide React** — icons
- **Tailwind CSS** (CDN)

## Setup

```bash
npm install

# Create .env.local
VITE_API_URL=http://localhost:5000   # or http://localhost:8000 for FastAPI

npm run dev     # http://localhost:3000
npm run build   # outputs to dist/
npm run preview # preview production build
```

## Structure

```
src/
  App.tsx                  ← root; manages analysis state, layout
  types.ts                 ← AccountInfo, Transaction, AnalysisResult, ApiResponse
  services/api.ts          ← uploadBankStatement(file) — POST to VITE_API_URL
  components/
    FileUpload.tsx          ← drag-drop + click; loading state; error alerts
    AccountOverview.tsx     ← bank details, account holder, confidence %, period
    AnalyticsCharts.tsx     ← balance history (line), income/expense (bar), merchants (pie)
    MerchantInsights.tsx    ← merchant table: count, avg/median amount, frequency
    TransactionTable.tsx    ← searchable list with date, narration, method, amount, balance
    ErrorBoundary.tsx       ← per-section error boundary
  index.tsx                ← React 19 DOM entry
```

No global state manager — all data flows top-down via props from `App.tsx`.

## Switching backends

To point at the FastAPI backend (port 8000), update `.env.local`:

```env
VITE_API_URL=http://localhost:8000
```

Both backends expose the same `POST /api/analyze/bank/statement` endpoint with identical JSON response shapes.
