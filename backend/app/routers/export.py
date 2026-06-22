import io
import re
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

    safe_name = re.sub(r"[^\w\-.]", "_", req.filename)

    rows = []
    for txn in req.transactions:
        rows.append(
            {
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
            }
        )

    df = pd.DataFrame(rows)

    if req.format == "csv":
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.csv"'},
        )

    # xlsx
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Transactions")
        worksheet = writer.sheets["Transactions"]
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            worksheet.column_dimensions[col[0].column_letter].width = min(
                max_len + 2, 50
            )
    output.seek(0)
    return StreamingResponse(
        iter([output.read()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.xlsx"'},
    )
