import logging

import pandas as pd
import pdfplumber

from app.enrichers.narration_enricher import analyze_narration_details
from app.parsers.excel_parser import (
    clean_column_name,
    deduplicate_transactions,
    find_column,
    normalize_date,
    parse_amount,
)
from app.scorers.confidence_scorer import calculate_confidence_score

logger = logging.getLogger(__name__)


def looks_like_header(row) -> bool:
    if not row:
        return False
    header_keywords = {
        "date",
        "narration",
        "description",
        "debit",
        "credit",
        "amount",
        "balance",
        "particulars",
        "withdrawal",
        "deposit",
        "txn",
        "transaction",
        "ref",
        "details",
        "chq",
    }
    row_text = " ".join(str(cell).lower() for cell in row if cell)
    return any(kw in row_text for kw in header_keywords)


def process_pdf_transactions(file_path: str, extract_metadata_fn) -> dict:
    try:
        transactions = []
        all_text = ""
        tables_df_list = []
        last_known_headers = None

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text(x_tolerance=1) or ""
                all_text += text + "\n"

                tables = page.extract_tables()
                for table_idx, table in enumerate(tables):
                    if not table or len(table) < 2:
                        continue
                    try:
                        if looks_like_header(table[0]):
                            headers = table[0]
                            rows = table[1:]
                            last_known_headers = headers
                        elif last_known_headers is not None:
                            logger.debug(
                                "[PDF] Continuation table detected on page %s — reusing header from previous page",
                                page_num + 1,
                            )
                            headers = last_known_headers
                            rows = table
                        else:
                            logger.warning(
                                "[PDF] First PDF table on page %s has no recognizable header — skipping",
                                page_num + 1,
                            )
                            continue

                        df = pd.DataFrame(rows, columns=headers)
                        df.columns = [clean_column_name(col) for col in df.columns]
                        tables_df_list.append(df)
                        logger.debug(
                            "Page %s, Table %s extracted with columns: %s",
                            page_num + 1,
                            table_idx + 1,
                            df.columns.tolist(),
                        )
                    except Exception as df_create_err:
                        logger.warning(
                            "Could not create DataFrame from PDF table on page %s, table %s: %s",
                            page_num + 1,
                            table_idx + 1,
                            df_create_err,
                        )

        if not tables_df_list:
            logger.warning("No tables found or extracted from PDF: %s", file_path)
            meta_info = extract_metadata_fn(all_text)
            return {
                "success": 0,
                "status_code": 400,
                "message": "No structured transaction tables could be extracted from the PDF.",
                "result": {"account_info": meta_info, "transactions": []},
            }

        for df in tables_df_list:
            date_col = find_column(
                ["date", "txn_date", "transaction_date", "value_date"], df.columns
            )
            credit_col = find_column(
                [
                    "credit",
                    "cr",
                    "credit_amount",
                    "received",
                    "deposit",
                    "cr_amount",
                    "deposits",
                ],
                df.columns,
            )
            debit_col = find_column(
                [
                    "debit",
                    "dr",
                    "debit_amount",
                    "withdraw",
                    "paid",
                    "dr_amount",
                    "withdrawals",
                ],
                df.columns,
            )
            amount_col = find_column(
                ["amount", "transaction_amount", "value"], df.columns
            )
            narration_col = find_column(
                [
                    "narration",
                    "description",
                    "details",
                    "remark",
                    "particulars",
                    "transaction_details",
                ],
                df.columns,
            )
            balance_col = find_column(
                ["balance", "closing_balance", "available_balance", "current_balance"],
                df.columns,
            )
            account_col = find_column(
                ["account", "acc_no", "account_number"], df.columns
            )

            required_cols_pdf = [date_col, narration_col]
            if not all(required_cols_pdf) or not (
                credit_col or debit_col or amount_col
            ):
                logger.warning(
                    "Skipping PDF table: missing critical columns. Date: %s, Narration: %s, Amount: %s/%s/%s",
                    date_col,
                    narration_col,
                    credit_col,
                    debit_col,
                    amount_col,
                )
                continue

            for _, row in df.iterrows():
                try:
                    amount = None
                    txn_type = None

                    credit = parse_amount(row.get(credit_col))
                    debit = parse_amount(row.get(debit_col))
                    general_amount = parse_amount(row.get(amount_col))

                    if credit is not None and credit > 0:
                        amount = credit
                        txn_type = "CREDIT"
                    elif debit is not None and debit > 0:
                        amount = debit
                        txn_type = "DEBIT"
                    elif general_amount is not None:
                        amount = general_amount
                        txn_type = "CREDIT" if amount >= 0 else "DEBIT"
                        amount = abs(amount)

                    if (
                        amount is None
                        and credit is None
                        and debit is None
                        and general_amount is None
                    ):
                        logger.debug("Skipping PDF row: no amount information found.")
                        continue

                    narration = (
                        str(row.get(narration_col)).strip()
                        if pd.notna(row.get(narration_col))
                        else ""
                    )
                    if not narration and amount is None:
                        logger.debug(
                            "Skipping PDF row: no narration or amount present."
                        )
                        continue

                    transaction_date_str = (
                        str(row.get(date_col)).strip()
                        if pd.notna(row.get(date_col))
                        else None
                    )
                    parsed_date = normalize_date(transaction_date_str)

                    balance = parse_amount(row.get(balance_col))
                    account = (
                        str(row.get(account_col)).strip()
                        if account_col and pd.notna(row.get(account_col))
                        else None
                    )

                    narration_details = analyze_narration_details(narration)

                    txn_obj = {
                        "transaction_date": parsed_date,
                        "transaction_type": txn_type,
                        "amount": amount,
                        "narration": narration,
                        "balance": balance,
                        "account": account,
                        **narration_details,
                    }
                    transactions.append(txn_obj)

                except Exception as row_err:
                    logger.warning(
                        "Skipping PDF row due to error: %s", row_err, exc_info=True
                    )

        meta_info = extract_metadata_fn(all_text)

        transactions = deduplicate_transactions(transactions)

        for txn in transactions:
            txn["confidence_score"] = calculate_confidence_score(txn)

        overall_confidence = (
            round(
                sum(t["confidence_score"] for t in transactions) / len(transactions),
                2,
            )
            if transactions
            else 0.0
        )

        return {
            "success": 1,
            "status_code": 200,
            "message": f"{len(transactions)} transactions parsed from PDF",
            "result": {
                "account_info": meta_info,
                "transactions": transactions,
                "confidence_summary": {
                    "overall_score": overall_confidence,
                    "total_transactions": len(transactions),
                    "high_confidence_txns": sum(
                        1 for t in transactions if t["confidence_score"] >= 0.85
                    ),
                },
            },
        }

    except Exception as e:
        logger.error(
            "Failed to analyze PDF bank statement: %s — %s",
            file_path,
            e,
            exc_info=True,
        )
        return {
            "success": 0,
            "status_code": 500,
            "message": "Failed to analyze PDF bank statement",
            "result": {"error": str(e)},
        }
