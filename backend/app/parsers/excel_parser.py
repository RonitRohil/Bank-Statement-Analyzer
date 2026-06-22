import csv as csv_mod
import logging
import re
from datetime import datetime

import pandas as pd

from app.enrichers.narration_enricher import analyze_narration_details
from app.scorers.confidence_scorer import calculate_confidence_score

logger = logging.getLogger(__name__)


def clean_column_name(col):
    if not isinstance(col, str):
        col = str(col)
    return (
        col.strip()
        .lower()
        .replace(" ", "_")
        .replace(".", "")
        .replace("/", "_")
        .replace("\\", "_")
        .replace("-", "_")
    )


def parse_amount(val):
    if (
        not val
        or pd.isna(val)
        or str(val).strip().lower() in ["", "nan", "none", "n/a", "-"]
    ):
        return None

    if isinstance(val, (pd.Series, dict)):
        logger.debug("[parse_amount] Skipping non-primitive value: %s", type(val))
        return None

    try:
        val_str = str(val).strip()

        if re.match(r"\d{4}[-/]\d{2}[-/]\d{2}", val_str):
            logger.debug("[parse_amount] Rejected date-like value: '%s'", val_str)
            return None

        val_str = (
            val_str.replace(",", "")
            .replace("₹", "")
            .replace("$", "")
            .replace("€", "")
            .replace("£", "")
        )

        val_str = re.sub(r"\b(?:Cr\.?|Dr\.?)", "", val_str, flags=re.IGNORECASE).strip()

        if val_str.startswith("(") and val_str.endswith(")"):
            val_str = "-" + val_str[1:-1]

        amount = float(val_str)
        if pd.isna(amount):
            return None
        return amount

    except ValueError:
        logger.debug(
            "[parse_amount] Could not parse amount: '%s'. Returning None.", val
        )
        return None
    except Exception as e:
        logger.debug("[parse_amount] Unexpected error parsing '%s': %s", val, e)
        return None


def find_column(possible_keywords, columns):
    normalized_columns = [col.strip().lower() for col in columns]

    for keyword in possible_keywords:
        keyword_clean = keyword.strip().lower()
        for i, col in enumerate(normalized_columns):
            if col == keyword_clean:
                return columns[i]

    for keyword in possible_keywords:
        keyword_clean = keyword.strip().lower()
        for i, col in enumerate(normalized_columns):
            if keyword_clean in col:
                return columns[i]

    return None


def detect_header_row(df_raw, max_rows_to_check=20):
    header_keywords = [
        "date",
        "transaction_date",
        "value_date",
        "description",
        "narration",
        "remark",
        "particulars",
        "credit",
        "debit",
        "balance",
        "amount",
        "txn_type",
        "type",
        "chq_no",
        "cheque_number",
        "withdrawals",
        "deposits",
    ]

    for i in range(min(max_rows_to_check, len(df_raw))):
        row = df_raw.iloc[i]
        match_count = 0
        for cell in row:
            if isinstance(cell, str):
                cleaned_cell = clean_column_name(cell)
                if any(keyword in cleaned_cell for keyword in header_keywords):
                    match_count += 1
        if match_count >= 2:
            logger.debug("Detected header row at index: %s", i)
            return i
    logger.debug("No clear header row detected, defaulting to row 0.")
    return 0


def normalize_date(date_input, row_index=None):
    if not date_input:
        return None

    if isinstance(date_input, (datetime, pd.Timestamp)):
        return date_input.strftime("%Y-%m-%d")

    if isinstance(date_input, str):
        date_input = date_input.strip()

        if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", date_input):
            try:
                parsed = datetime.strptime(date_input, "%Y-%m-%d %H:%M:%S")
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                pass

        possible_formats = [
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%d-%b-%y",
            "%d-%b-%Y",
            "%d - %b - %Y",
            "%Y-%m-%d",
        ]

        for fmt in possible_formats:
            try:
                parsed = datetime.strptime(date_input, fmt)
                logger.debug(
                    "[Parsed] Row %s: '%s' → %s using %s",
                    row_index,
                    date_input,
                    parsed.strftime("%Y-%m-%d"),
                    fmt,
                )
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue

    try:
        parsed = pd.to_datetime(date_input, errors="coerce", dayfirst=False)
        if pd.notna(parsed):
            logger.debug(
                "[Pandas Parsed] Row %s: '%s' → %s",
                row_index,
                date_input,
                parsed.strftime("%Y-%m-%d"),
            )
            return parsed.strftime("%Y-%m-%d")
    except Exception as e:
        logger.debug("[Fallback Error] Row %s: '%s' — %s", row_index, date_input, e)

    logger.warning("[Failed to Parse] Row %s: '%s'", row_index, date_input)
    return date_input


def deduplicate_transactions(transactions: list[dict]) -> list[dict]:
    """Remove exact duplicates by (date, amount, narration, balance). No logging — caller logs."""
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for txn in transactions:
        key = (
            txn.get("transaction_date"),
            txn.get("amount"),
            txn.get("narration", "")[:100],
            txn.get("balance"),
        )
        if key not in seen:
            seen.add(key)
            deduped.append(txn)
    return deduped


def read_csv_raw(file_path):
    rows = []
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            with open(file_path, "r", encoding=encoding, newline="") as f:
                rows = list(csv_mod.reader(f))
            break
        except (UnicodeDecodeError, Exception):
            rows = []
    if not rows:
        return pd.DataFrame()
    max_cols = max((len(r) for r in rows), default=0)
    padded = [r + [""] * (max_cols - len(r)) for r in rows]
    return pd.DataFrame(padded, dtype=str)


def process_excel_csv(file_path: str, extract_metadata_fn) -> dict:
    try:
        if file_path.endswith(".csv"):
            raw_df = read_csv_raw(file_path)
        else:
            raw_df = pd.read_excel(file_path, header=None, dtype=str)

        header_row_index = detect_header_row(raw_df)

        if file_path.endswith(".csv"):
            skip_rows = list(range(header_row_index))
            df = pd.read_csv(
                file_path,
                skiprows=skip_rows,
                header=0,
                dtype=str,
                on_bad_lines="skip",
            )
        else:
            df = pd.read_excel(file_path, header=header_row_index, dtype=str)

        df = df.loc[:, ~df.columns.str.contains("^Unnamed", case=False, na=False)]
        df.columns = [clean_column_name(col) for col in df.columns]
        logger.debug("Excel/CSV Normalized Columns: %s", df.columns.tolist())

        transaction_date_col = find_column(
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
            ["amount", "transaction_amount", "value"],
            [col for col in df.columns if "date" not in col.lower()],
        )
        narration_col = find_column(
            ["narration", "description", "remark", "details", "transaction_details"],
            df.columns,
        )
        balance_col = find_column(
            ["balance", "closing_balance", "available_balance", "current_balance"],
            df.columns,
        )
        account_col = find_column(["account", "acc_no", "account_number"], df.columns)

        reserved_non_amount_cols = {
            transaction_date_col,
            narration_col,
            balance_col,
            account_col,
        }
        if credit_col in reserved_non_amount_cols:
            credit_col = None
        if debit_col in reserved_non_amount_cols:
            debit_col = None

        dr_cr_type_col = None
        for col in df.columns:
            if "dr" in col and "cr" in col:
                dr_cr_type_col = col
                break
        if dr_cr_type_col:
            if credit_col == dr_cr_type_col:
                credit_col = None
            if debit_col == dr_cr_type_col:
                debit_col = None

        required_cols = [transaction_date_col, narration_col]
        if not all(required_cols) or not (credit_col or debit_col or amount_col):
            logger.warning(
                "Missing critical columns in %s. Date: %s, Narration: %s, Amount: %s/%s/%s",
                file_path,
                transaction_date_col,
                narration_col,
                credit_col,
                debit_col,
                amount_col,
            )
            return {
                "success": 0,
                "status_code": 400,
                "message": "Missing critical columns (Date, Narration, and at least one of Credit/Debit/Amount).",
                "result": {},
            }

        transactions = []

        for index, row in df.iterrows():
            try:
                amount = None
                txn_type = None

                credit = parse_amount(row.get(credit_col))
                debit = parse_amount(row.get(debit_col))
                general_amount = (
                    parse_amount(row.get(amount_col)) if amount_col else None
                )

                if credit is not None and credit > 0:
                    amount = credit
                    txn_type = "CREDIT"
                elif debit is not None and debit > 0:
                    amount = debit
                    txn_type = "DEBIT"
                elif general_amount is not None:
                    amount = abs(general_amount)
                    if dr_cr_type_col:
                        dr_cr_raw = row.get(dr_cr_type_col)
                        dr_cr_val = (
                            str(dr_cr_raw).strip().lower()
                            if pd.notna(dr_cr_raw)
                            else ""
                        )
                        txn_type = (
                            "CREDIT"
                            if "cr" in dr_cr_val
                            else (
                                "DEBIT"
                                if "dr" in dr_cr_val
                                else ("CREDIT" if general_amount >= 0 else "DEBIT")
                            )
                        )
                    else:
                        txn_type = "CREDIT" if general_amount >= 0 else "DEBIT"

                if (
                    amount is None
                    and credit is None
                    and debit is None
                    and general_amount is None
                ):
                    logger.debug("Skipping row %s: No valid amount found.", index)
                    continue

                narration = (
                    str(row.get(narration_col)).strip()
                    if pd.notna(row.get(narration_col))
                    else ""
                )

                if not narration and amount is None:
                    logger.debug(
                        "Skipping row %s: No narration or amount present.", index
                    )
                    continue

                transaction_date_str = (
                    str(row.get(transaction_date_col)).strip()
                    if pd.notna(row.get(transaction_date_col))
                    else None
                )
                parsed_date = normalize_date(transaction_date_str, index)

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

            except Exception as inner_err:
                logger.warning(
                    "Skipping row %s due to parsing error: %s",
                    index,
                    inner_err,
                    exc_info=True,
                )

        meta_info = extract_metadata_fn(raw_df)

        transactions = deduplicate_transactions(transactions)

        for txn in transactions:
            txn["confidence_score"] = calculate_confidence_score(txn)

        if transactions:
            overall_confidence = round(
                sum(txn["confidence_score"] for txn in transactions)
                / len(transactions),
                2,
            )
        else:
            overall_confidence = 0.0

        return {
            "success": 1,
            "status_code": 200,
            "message": f"{len(transactions)} transactions parsed from Excel/CSV",
            "result": {
                "account_info": meta_info,
                "transactions": transactions,
                "confidence_summary": {
                    "overall_score": overall_confidence,
                    "total_transactions": len(transactions),
                    "high_confidence_txns": sum(
                        1 for txn in transactions if txn["confidence_score"] >= 0.85
                    ),
                },
            },
        }

    except Exception as e:
        logger.error(
            "Failed to analyze Excel/CSV bank statement: %s — %s",
            file_path,
            e,
            exc_info=True,
        )
        return {
            "success": 0,
            "status_code": 500,
            "message": "Failed to analyze Excel/CSV bank statement",
            "result": {"error": str(e)},
        }
