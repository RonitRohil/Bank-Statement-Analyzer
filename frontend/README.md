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

# Create .env.local — points at the active FastAPI backend
VITE_API_URL=http://localhost:8000

npm run dev     # http://localhost:3000
npm run build   # outputs to dist/
npm run preview # preview production build
```

## Structure

Components live at the project root (no `src/` directory):

```
App.tsx                  ← root; manages analysis state, layout
types.ts                 ← AccountInfo, Transaction, AnalysisResult, ApiResponse
services/api.ts          ← uploadBankStatement(file) — POST to ${VITE_API_URL}
index.html               ← Vite entry
components/
  FileUpload.tsx          ← drag-drop + click; loading state; error alerts
  AccountOverview.tsx     ← bank details, account holder, confidence %, period
  AnalyticsCharts.tsx     ← balance history (line), income/expense (bar), merchants (pie)
  MerchantInsights.tsx    ← merchant table: count, avg/median amount, frequency
  TransactionTable.tsx    ← list with date, narration, method, amount, balance, type
  ErrorBoundary.tsx       ← per-section error boundary
```

No global state manager — all data flows top-down via props from `App.tsx`.

## Backend

The app targets the **FastAPI backend on port 8000** via `VITE_API_URL`. The deprecated Flask backend (port 5000) is being removed in Sprint-03; don't point at it.

## Known issues (open)

- **TD-037:** two network-error messages and the env fallback still mention `localhost:5000` — cosmetic but misleading post-cutover. Fix: centralize on an exported `API_BASE` (default 8000).
- **TD-038:** the backend now exposes `POST /api/analyze/bank/summary` (income/expense/net, top categories/merchants) and a `llm_enriched` flag on transactions, but **neither is rendered yet**. A summary card + an "AI-categorized" badge are planned for Sprint-03 (BSA-12).
- **TD-018:** `TransactionTable` renders every row (no virtualization) — add pagination before large/multi-statement data lands.

See `docs/code-review.md` and `docs/tech-debt.md` for detail.
