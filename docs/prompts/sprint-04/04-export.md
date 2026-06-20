# Prompt 04 — BSA-13: CSV / Excel Export

## Task: Add a download endpoint + frontend button so users can export parsed transactions

**Context:** The single most common user request for a bank statement parser is "let me get this data out." The parsed JSON already contains clean, normalized transactions — exporting to CSV or Excel is a pure I/O operation using pandas and openpyxl, both already in `requirements.txt`.

**Files to read first:**
- `backend/app/models/schemas.py` — `Transaction` schema (fields to export)
- `backend/app/routers/analyze.py` — pattern to follow for a new router
- `backend/app/main.py` — where to register the new router
- `frontend/components/TransactionTable.tsx` — where the download button will live
- `frontend/types.ts` — `Transaction` interface

---

## Change 1 — New export endpoint

**File (new):** `backend/app/routers/export.py`

```python
import io
import json
from typing import Literal
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.models.schemas import Transaction

router = APIRouter()


class ExportRequest(BaseModel):
    transactions: list[Transaction]
    format: Literal["csv", "xlsx"] = "csv"
    filename: str = "transactions"


@router.post("/api/export/transactions")
def export_transactions(req: ExportRequest):
    if not req.transactions:
        raise HTTPException(status_code=400, detail="No transactions to export")

    rows = []
    for txn in req.transactions:
        rows.append({
            "Date": txn.transaction_date,
            "Type": txn.transaction_type,
            "Amount": txn.amount,
            "Balance": txn.balance,
            "Narration": txn.narration,
            "Payment Method": txn.payment_method,
            "Merchant": txn.merchant,
            "Category": ", ".join(txn.category) if txn.category else "",
            "UPI ID": txn.upi_id,
            "Reference": txn.transaction_reference,
            "Bank Peer": txn.bank_peer,
            "Payment Gateway": txn.payment_gateway,
            "Confidence": txn.confidence_score,
            "AI Categorized": txn.llm_enriched or False,
        })

    df = pd.DataFrame(rows)

    if req.format == "csv":
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{req.filename}.csv"'},
        )

    # xlsx
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Transactions")
        # Auto-fit column widths
        worksheet = writer.sheets["Transactions"]
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            worksheet.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)
    output.seek(0)
    return StreamingResponse(
        iter([output.read()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{req.filename}.xlsx"'},
    )
```

**Register in `backend/app/main.py`:**

```python
from app.routers import export
app.include_router(export.router)
```

**Constraints:**
- Use `StreamingResponse` — don't write temp files to disk.
- `Category` is a list; join with `", "` for CSV/Excel readability.
- Column width auto-fit is a nice-to-have; keep it simple (don't break on empty sheets).
- The `filename` parameter lets the frontend pass a meaningful name (e.g., `"HDFC_Jan_2026"`).

---

## Change 2 — Frontend export function in api.ts

**File:** `frontend/services/api.ts`

Add:

```typescript
export async function exportTransactions(
  transactions: Transaction[],
  format: "csv" | "xlsx",
  filename: string = "transactions"
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/export/transactions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transactions, format, filename }),
  });

  if (!response.ok) {
    throw new Error(`Export failed: ${response.statusText}`);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}.${format}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
```

---

## Change 3 — Download buttons in TransactionTable

**File:** `frontend/components/TransactionTable.tsx`

Add two export buttons in the table header row (next to the search box). The `TransactionTable` component already receives `transactions` as a prop — pass them to `exportTransactions`.

```tsx
import { exportTransactions } from "../services/api";
import { useState } from "react";

// Inside the component, before return:
const [exporting, setExporting] = useState(false);

const handleExport = async (format: "csv" | "xlsx") => {
  setExporting(true);
  try {
    await exportTransactions(transactions, format, "bank_statement");
  } catch (err) {
    console.error("Export error:", err);
  } finally {
    setExporting(false);
  }
};

// In the JSX, next to the search input:
<div className="flex gap-2">
  <button
    onClick={() => handleExport("csv")}
    disabled={exporting || transactions.length === 0}
    className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-md hover:bg-slate-50 disabled:opacity-50"
  >
    {exporting ? "Exporting…" : "↓ CSV"}
  </button>
  <button
    onClick={() => handleExport("xlsx")}
    disabled={exporting || transactions.length === 0}
    className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-md hover:bg-slate-50 disabled:opacity-50"
  >
    {exporting ? "Exporting…" : "↓ Excel"}
  </button>
</div>
```

**Constraints:**
- Buttons must be disabled while `exporting` is true — prevent double-click.
- Buttons must be disabled when `transactions.length === 0`.
- Don't change the existing search/filter logic.
- The download uses the browser's native download mechanism — no modal or toast required.

---

## Tests

**File:** `backend/tests/test_export.py`

```python
import pytest

def test_export_csv(client, sample_transactions_payload):
    response = client.post("/api/export/transactions", json={
        "transactions": sample_transactions_payload,
        "format": "csv",
        "filename": "test"
    })
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "Date,Type,Amount" in response.text

def test_export_xlsx(client, sample_transactions_payload):
    response = client.post("/api/export/transactions", json={
        "transactions": sample_transactions_payload,
        "format": "xlsx",
        "filename": "test"
    })
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    assert len(response.content) > 0

def test_export_empty_returns_400(client):
    response = client.post("/api/export/transactions", json={
        "transactions": [],
        "format": "csv"
    })
    assert response.status_code == 400
```

Define `sample_transactions_payload` as a fixture in `conftest.py` — a list of 2–3 minimal valid transaction dicts.

---

## Documentation

1. `docs/changelog.md` — add entry for BSA-13.
2. `docs/tech-debt.md` — mark BSA-13 as ✅ done.

**Verification:**

```bash
cd backend && pytest tests/test_export.py -v
```

Run the full app. Upload a statement. Click "↓ CSV" — browser should download `bank_statement.csv`. Open it — rows should match the transaction table.
