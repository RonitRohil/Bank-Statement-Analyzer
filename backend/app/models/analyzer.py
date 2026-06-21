import csv as csv_mod
import logging
import pandas as pd
import pdfplumber
import re
import os
from datetime import datetime
from collections import defaultdict

from app.services.categories import REGEX_TO_CANONICAL

logger = logging.getLogger(__name__)


class BankStatementAnalyzer:

    def __init__(self, file_path):
        self.file_path = file_path

    @staticmethod
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

    @staticmethod
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

            # Reject date-like formats (e.g. '2025-02-05', '2025/02/05', '2025-02-05 00:00:00')
            if re.match(r"\d{4}[-/]\d{2}[-/]\d{2}", val_str):
                logger.debug("[parse_amount] Rejected date-like value: '%s'", val_str)
                return None

            # Remove currency and non-numeric symbols
            val_str = (
                val_str.replace(",", "")
                .replace("₹", "")
                .replace("$", "")
                .replace("€", "")
                .replace("£", "")
            )

            # Remove 'Cr.' or 'Dr.'
            val_str = re.sub(
                r"\b(?:Cr\.?|Dr\.?)", "", val_str, flags=re.IGNORECASE
            ).strip()

            # Handle negative in parentheses e.g., "(100.00)"
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

    @staticmethod
    def find_column(possible_keywords, columns):
        # Normalize columns (strip and lowercase)
        normalized_columns = [col.strip().lower() for col in columns]

        # First pass: Exact match (case-insensitive)
        for keyword in possible_keywords:
            keyword_clean = keyword.strip().lower()
            for i, col in enumerate(normalized_columns):
                if col == keyword_clean:
                    return columns[i]  # Return original column name

        # Second pass: Partial match (case-insensitive)
        for keyword in possible_keywords:
            keyword_clean = keyword.strip().lower()
            for i, col in enumerate(normalized_columns):
                if keyword_clean in col:
                    return columns[i]  # Return original column name

        return None

    @staticmethod
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
                    cleaned_cell = BankStatementAnalyzer.clean_column_name(cell)
                    if any(keyword in cleaned_cell for keyword in header_keywords):
                        match_count += 1
            if match_count >= 2:  # Threshold: at least 2 matching keywords
                logger.debug("Detected header row at index: %s", i)
                return i
        logger.debug("No clear header row detected, defaulting to row 0.")
        return 0  # Fallback to row 0

    @staticmethod
    def _looks_like_header(row):
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

    def _get_statement_range_from_df(self, df):
        date_col = self.find_column(
            ["date", "txn_date", "transaction_date", "value_date"], df.columns
        )
        if date_col:
            # Attempt to parse dates robustly
            dates = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
            valid_dates = dates.dropna()
            if not valid_dates.empty:
                return {
                    "from": valid_dates.min().strftime("%Y-%m-%d"),
                    "to": valid_dates.max().strftime("%Y-%m-%d"),
                }

        logger.debug("Could not determine statement date range.")
        return {}

    def extract_transactions(self):
        file_extension = os.path.splitext(self.file_path)[1].lower()

        if file_extension in (".csv", ".xlsx", ".xls"):
            return self._process_excel_csv()
        elif file_extension == ".pdf":
            return self._process_pdf_transactions()
        else:
            logger.warning("Unsupported file type: %s", file_extension)
            return {
                "success": 0,
                "status_code": 400,
                "message": "Unsupported file type",
                "result": {},
            }

    def _deduplicate_transactions(self, transactions: list[dict]) -> list[dict]:
        """Remove exact duplicates by (date, amount, narration, balance). Keeps first occurrence."""
        seen: set[tuple] = set()
        deduped: list[dict] = []
        dropped = 0
        for txn in transactions:
            key = (
                txn.get("transaction_date"),
                txn.get("amount"),
                txn.get("narration", "")[:100],
                txn.get("balance"),
            )
            if key in seen:
                dropped += 1
                continue
            seen.add(key)
            deduped.append(txn)
        if dropped > 0:
            logger.info("[DEDUP] Removed %d duplicate transaction(s)", dropped)
        return deduped

    @staticmethod
    def _read_csv_raw(file_path):
        """Read a CSV using Python's csv module to handle variable-width metadata rows.
        Returns a DataFrame where every row is padded to the max column count."""
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

    def _process_excel_csv(self):
        try:
            if self.file_path.endswith(".csv"):
                raw_df = self._read_csv_raw(self.file_path)
            else:
                raw_df = pd.read_excel(self.file_path, header=None, dtype=str)

            header_row_index = self.detect_header_row(raw_df)

            # Read again with the detected header; skip metadata rows above the header
            # so pandas only sees consistent-width rows and won't error on field count.
            if self.file_path.endswith(".csv"):
                skip_rows = list(range(header_row_index))
                df = pd.read_csv(
                    self.file_path,
                    skiprows=skip_rows,
                    header=0,
                    dtype=str,
                    on_bad_lines="skip",
                )
            else:
                df = pd.read_excel(self.file_path, header=header_row_index, dtype=str)

            # Drop unnamed columns (often created by pandas for empty columns)
            df = df.loc[:, ~df.columns.str.contains("^Unnamed", case=False, na=False)]
            df.columns = [self.clean_column_name(col) for col in df.columns]
            logger.debug("Excel/CSV Normalized Columns: %s", df.columns.tolist())

            # Detect Key Columns
            transaction_date_col = self.find_column(
                ["date", "txn_date", "transaction_date", "value_date"], df.columns
            )
            credit_col = self.find_column(
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
            debit_col = self.find_column(
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
            amount_col = self.find_column(
                ["amount", "transaction_amount", "value"],
                [col for col in df.columns if "date" not in col.lower()],
            )
            # Fallback if credit/debit not explicit
            narration_col = self.find_column(
                [
                    "narration",
                    "description",
                    "remark",
                    "details",
                    "transaction_details",
                ],
                df.columns,
            )
            balance_col = self.find_column(
                ["balance", "closing_balance", "available_balance", "current_balance"],
                df.columns,
            )
            account_col = self.find_column(
                ["account", "acc_no", "account_number"], df.columns
            )

            # Guard: partial keyword matching can false-positive on reserved columns.
            # "cr" is a substring of "description" → credit_col gets the narration col.
            # Clear any credit/debit match that landed on a non-amount column.
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

            # Detect "Amount + Dr/Cr label" pattern (e.g., Kotak "Dr / Cr" column).
            # A column whose cleaned name contains BOTH "dr" and "cr" is a text label
            # ("Dr"/"Cr"), not a numeric amount.  Promote the first such column to
            # dr_cr_type_col and clear it from credit/debit detection.
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
                    self.file_path,
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

                    credit = self.parse_amount(row.get(credit_col))
                    debit = self.parse_amount(row.get(debit_col))

                    general_amount = (
                        self.parse_amount(row.get(amount_col)) if amount_col else None
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
                    parsed_date = self.normalize_date(transaction_date_str, index)

                    balance = self.parse_amount(row.get(balance_col))
                    account = (
                        str(row.get(account_col)).strip()
                        if account_col and pd.notna(row.get(account_col))
                        else None
                    )

                    narration_details = self.analyze_narration_details(narration)

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

            meta_info = self._extract_metadata_from_df(raw_df)

            transactions = self._deduplicate_transactions(transactions)

            for txn in transactions:
                txn["confidence_score"] = self.calculate_confidence_score(txn)

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
                    "merchant_insights": TransactionPatternTrainer().analyze(
                        transactions
                    ),
                },
            }

        except Exception as e:
            logger.error(
                "Failed to analyze Excel/CSV bank statement: %s — %s",
                self.file_path,
                e,
                exc_info=True,
            )
            return {
                "success": 0,
                "status_code": 500,
                "message": "Failed to analyze Excel/CSV bank statement",
                "result": {"error": str(e)},
            }

    def _process_pdf_transactions(self):
        try:
            transactions = []
            all_text = ""
            tables_df_list = []
            last_known_headers = None

            with pdfplumber.open(self.file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    text = (
                        page.extract_text(x_tolerance=1) or ""
                    )  # x_tolerance helps with column alignment
                    all_text += text + "\n"

                    tables = page.extract_tables()
                    for table_idx, table in enumerate(tables):
                        if not table or len(table) < 2:
                            continue
                        try:
                            if self._looks_like_header(table[0]):
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
                            df.columns = [
                                self.clean_column_name(col) for col in df.columns
                            ]
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
                logger.warning(
                    "No tables found or extracted from PDF: %s", self.file_path
                )
                meta_info = self._extract_metadata_from_text(all_text)
                return {
                    "success": 0,
                    "status_code": 400,
                    "message": "No structured transaction tables could be extracted from the PDF.",
                    "result": {"account_info": meta_info, "transactions": []},
                }

            for df in tables_df_list:
                date_col = self.find_column(
                    ["date", "txn_date", "transaction_date", "value_date"], df.columns
                )
                credit_col = self.find_column(
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
                debit_col = self.find_column(
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
                amount_col = self.find_column(
                    ["amount", "transaction_amount", "value"], df.columns
                )
                narration_col = self.find_column(
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
                balance_col = self.find_column(
                    [
                        "balance",
                        "closing_balance",
                        "available_balance",
                        "current_balance",
                    ],
                    df.columns,
                )
                account_col = self.find_column(
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

                        credit = self.parse_amount(row.get(credit_col))
                        debit = self.parse_amount(row.get(debit_col))
                        general_amount = self.parse_amount(row.get(amount_col))

                        if credit is not None and credit > 0:
                            amount = credit
                            txn_type = "CREDIT"
                        elif debit is not None and debit > 0:
                            amount = debit
                            txn_type = "DEBIT"
                        elif general_amount is not None:
                            amount = general_amount
                            txn_type = "CREDIT" if amount >= 0 else "DEBIT"
                            amount = abs(amount)  # Ensure amount is positive

                        if (
                            amount is None
                            and credit is None
                            and debit is None
                            and general_amount is None
                        ):
                            logger.debug(
                                "Skipping PDF row: no amount information found."
                            )
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
                        parsed_date = self.normalize_date(transaction_date_str)

                        balance = self.parse_amount(row.get(balance_col))
                        account = (
                            str(row.get(account_col)).strip()
                            if account_col and pd.notna(row.get(account_col))
                            else None
                        )

                        narration_details = self.analyze_narration_details(narration)

                        txn_obj = {
                            "transaction_date": parsed_date,
                            "transaction_type": txn_type,
                            "amount": amount,
                            "narration": narration,
                            "balance": balance,
                            "account": account,
                            **narration_details,  # Merged analysis results
                        }
                        transactions.append(txn_obj)

                    except Exception as row_err:
                        logger.warning(
                            "Skipping PDF row due to error: %s", row_err, exc_info=True
                        )

            # Account metadata from full text
            meta_info = self._extract_metadata_from_text(all_text)

            transactions = self._deduplicate_transactions(transactions)

            # Score confidence for every transaction (consistent with Excel path)
            for txn in transactions:
                txn["confidence_score"] = self.calculate_confidence_score(txn)

            overall_confidence = (
                round(
                    sum(t["confidence_score"] for t in transactions)
                    / len(transactions),
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
                    "merchant_insights": TransactionPatternTrainer().analyze(
                        transactions
                    ),
                },
            }

        except Exception as e:
            logger.error(
                "Failed to analyze PDF bank statement: %s — %s",
                self.file_path,
                e,
                exc_info=True,
            )
            return {
                "success": 0,
                "status_code": 500,
                "message": "Failed to analyze PDF bank statement",
                "result": {"error": str(e)},
            }

    def normalize_date(self, date_input, row_index=None):
        """
        Normalize various date formats to 'YYYY-MM-DD'. Handles:
        - string dates in various formats
        - datetime-like objects
        - fallback to pandas only if needed
        """

        if not date_input:
            return None

        # ✅ Step 1: Already a datetime object (from Excel engine)
        if isinstance(date_input, (datetime, pd.Timestamp)):
            return date_input.strftime("%Y-%m-%d")

        # ✅ Step 2: Looks like a datetime string (e.g., '2025-02-04 00:00:00')
        if isinstance(date_input, str):
            date_input = date_input.strip()

            # Special case: looks like full datetime (YYYY-MM-DD HH:MM:SS)
            if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", date_input):
                try:
                    parsed = datetime.strptime(date_input, "%Y-%m-%d %H:%M:%S")
                    return parsed.strftime("%Y-%m-%d")
                except ValueError:
                    pass

            # ✅ Step 3: Try known formats
            possible_formats = [
                "%d-%m-%Y",
                "%d/%m/%Y",
                "%d-%b-%y",  # 01-Feb-25
                "%d-%b-%Y",
                "%d - %b - %Y",  # 01 - Feb - 2025
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

        # ✅ Step 4: Fallback to pandas only if nothing else worked
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

    def _extract_metadata_from_df(self, raw_df, max_lines=30):
        try:
            lines = (
                raw_df.iloc[:max_lines].fillna("").astype(str).values.flatten().tolist()
            )
            text_blob = " ".join([line.strip() for line in lines if line.strip()])

            metadata = self._extract_metadata_from_text(text_blob)

            # Re-read df with detected header to get accurate date column for range
            try:
                header_row_index = self.detect_header_row(raw_df)
                if self.file_path.endswith(".csv"):
                    skip_rows = list(range(header_row_index))
                    df_for_dates = pd.read_csv(
                        self.file_path,
                        skiprows=skip_rows,
                        header=0,
                        dtype=str,
                        on_bad_lines="skip",
                    )
                else:
                    df_for_dates = pd.read_excel(
                        self.file_path, header=header_row_index, dtype=str
                    )
                df_for_dates.columns = [
                    self.clean_column_name(col) for col in df_for_dates.columns
                ]
                metadata["statement_period"] = self._get_statement_range_from_df(
                    df_for_dates
                )
            except Exception as e:
                logger.warning(
                    "Could not determine statement range from excel for metadata: %s", e
                )
                metadata["statement_period"] = {}

            logger.debug("Extracted Metadata: %s", metadata)
            return metadata

        except Exception as e:
            logger.error(
                "[Metadata Extraction Error - Excel/CSV]: %s", e, exc_info=True
            )
            return {}

    def _extract_metadata_from_text(self, text_blob):
        metadata = {
            "account_number": None,
            "account_holder": None,
            "bank_name": None,
            "branch": None,
            "ifsc_code": None,
            "phone": None,
            "email": None,
            "statement_period": None,
        }

        # More robust patterns for key fields
        patterns = {
            "account_number": [
                r"(?:account|a/c|acct)\s*(?:no|num|number)?\s*[:\.]?\s*(\d{9,18})\b",  # General account numbers
                r"\b(\d{3,5}(?:-\d{2,5}){2,})\b",  # Some specific formatted account numbers
                r"\b(?:[Ii]nd[Oo]\s*)?(\d{11})\b",  # For Indian Bank accounts if specific format
            ],
            "account_holder": [
                r"(?:account\s*holder(?:\s*name)?|customer\s*(?:full\s*)?name|a/c\s*holder)\s*[:\.,]?\s*([A-Z][A-Za-z\s\.&,']{2,50}?)(?=\s+(?:Branch|Bank|Account\s*N|IFSC|Phone|Mobile|Email|Nomination|Currency|Statement|Address|Opening|Closing|\d{4,}|$))",
                r"(?:holder\s*name|name\s*of\s*(?:account\s*holder|customer))\s*[:\.]?\s*([A-Z][A-Za-z\s\.]{2,40}?)(?=\s+\w+\s*[:\.,]|\s*$)",
            ],
            "bank_name": [
                r"\b(STATE BANK OF INDIA|HDFC BANK|ICICI BANK|AXIS BANK|PUNJAB NATIONAL BANK|YES BANK|KOTAK MAHINDRA BANK|UNION BANK OF INDIA|CANARA BANK|INDIAN BANK|INDUSIND BANK|FEDERAL BANK|RBL BANK|BANDHAN BANK|IDFC FIRST BANK)\b",
                r"(?:bank\s*name|issued\s*by)\s*[:\.]?\s*([A-Z][A-Za-z\s,.]+?)(?=\s+(?:account|branch|ifsc|\d))",
                r"BANK NAME\s*[:\.]?\s*([A-Z\s&.]+)",
            ],
            "branch": [
                r"(?:branch\s*(?:name)?)\s*[:\.,]?\s*([A-Z][A-Za-z\s,.-]{2,40}?)(?=\s+(?:INDIA\b|IFSC|Nomination|Account|Customer|Currency|Statement|Phone|Mobile|Email|Opening|Closing|[A-Z]{4}0|\d{6,}|$))",
                r"BRANCH\s*[:\.,]\s*([A-Z][A-Za-z\s&.-]{2,40}?)(?=\s+(?:INDIA\b|IFSC|Nomination|\d{6,}|$))",
            ],
            "ifsc_code": [
                r"\b([A-Z]{4}0[A-Z0-9]{6})\b",  # Standard IFSC code pattern
                r"(?:IFSC\s*Code|IFSC)\s*[:\.]?\s*([A-Z]{4}0[A-Z0-9]{6})\b",
            ],
            "phone": [
                r"(?:tel|phone|mobile|mob|ph\.?)\s*[:\.]?\s*(\+?91[-\s]?[6-9]\d{9}|[6-9]\d{9})",
                r"(\+91[-\s]?[6-9]\d{9})\b",
            ],
            "email": [
                r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}\b",
            ],
        }

        for field, regex_list in patterns.items():
            for regex in regex_list:
                match = re.search(regex, text_blob, re.IGNORECASE)
                if match:
                    metadata[field] = match.group(1).strip()
                    break

        if not metadata["bank_name"] and metadata.get("ifsc_code"):
            _ifsc_bank_map = {
                "KKBK": "Kotak Mahindra Bank",
                "HDFC": "HDFC Bank",
                "ICIC": "ICICI Bank",
                "UTIB": "Axis Bank",
                "SBIN": "State Bank of India",
                "PUNB": "Punjab National Bank",
                "YESB": "Yes Bank",
                "CNRB": "Canara Bank",
                "IOBA": "Indian Overseas Bank",
                "BARB": "Bank of Baroda",
                "UBIN": "Union Bank of India",
                "INDB": "IndusInd Bank",
                "FDRL": "Federal Bank",
                "RATN": "RBL Bank",
                "BDBL": "Bandhan Bank",
                "IDFB": "IDFC FIRST Bank",
            }
            metadata["bank_name"] = _ifsc_bank_map.get(
                metadata["ifsc_code"][:4].upper()
            )

        date_patterns = [
            r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b",  # DD/MM/YYYY or DD-MM-YYYY
            r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\b",  # DD Mon YYYY
            r"\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b",  # YYYY-MM-DD or YYYY/MM/DD
        ]

        all_found_dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text_blob, re.IGNORECASE)
            for d_str in matches:
                try:
                    # Attempt to parse, coerce errors
                    parsed_d = pd.to_datetime(d_str, errors="coerce", dayfirst=True)
                    if pd.notna(parsed_d):
                        all_found_dates.append(parsed_d)
                except Exception:
                    pass

        if len(all_found_dates) >= 2:
            min_date = min(all_found_dates).strftime("%Y-%m-%d")
            max_date = max(all_found_dates).strftime("%Y-%m-%d")
            metadata["statement_period"] = {"from": min_date, "to": max_date}
        elif len(all_found_dates) == 1:
            metadata["statement_period"] = {
                "date": all_found_dates[0].strftime("%Y-%m-%d")
            }
        else:
            metadata["statement_period"] = {}

        logger.debug("Extracted Metadata: %s", metadata)
        return metadata

    @staticmethod
    def analyze_narration_details(narration):
        result = {
            "payment_method": None,
            "upi_id": None,
            "transaction_reference": None,
            "receiver_details": {
                "name": None,
                "account": None,
                "vpa": None,
            },  # Expanded receiver details
            "bank_peer": None,
            "merchant": None,
            "category": [],
            "remarks": [],
            "payment_gateway": None,  # e.g., PAYTM, RAZORPAY
        }

        if not narration:
            return result

        narration_upper = narration.upper()

        upi_structured_match = re.search(
            r"UPI\/(?P<upi_id>[^\/]+)\/(?P<remark>[^\/]+)\/(?P<bank>[^\/]+)\/(?P<txn_id>[^\s\/]+)",
            narration_upper,
        )
        if upi_structured_match:
            result["payment_method"] = "UPI"
            result["upi_id"] = upi_structured_match.group("upi_id").strip()
            result["transaction_reference"] = upi_structured_match.group(
                "txn_id"
            ).strip()
            result["bank_peer"] = upi_structured_match.group("bank").strip()
            result["remarks"].append(upi_structured_match.group("remark").strip())
            return result

        vsi_pattern = re.search(
            r"VSI\/(?P<merchant>[^\/]+)\/(?P<datetime>[^\/]+)\/(?P<txn_id>[^\s\/]+)",
            narration_upper,
        )
        if vsi_pattern:
            result["payment_method"] = "CARD"
            result["merchant"] = vsi_pattern.group("merchant").strip()
            result["transaction_reference"] = vsi_pattern.group("txn_id").strip()
            return result

        imps_transfer_match = re.search(
            r"IMPS/(\d{10,})/([^/]+)/([^/]+)", narration_upper
        )
        if imps_transfer_match:
            result["payment_method"] = "IMPS"
            result["transaction_reference"] = imps_transfer_match.group(1).strip()
            result["receiver_details"]["name"] = imps_transfer_match.group(2).strip()
            result["bank_peer"] = imps_transfer_match.group(3).strip()
            result["remarks"].append("IMPS TRANSFER")
            return result

        payment_methods_keywords = {
            "UPI": ["UPI", "IMPS/P2M", "PHONEPE", "GPAY", "PAYTM"],
            "IMPS": ["IMPS", "IMPS/P2A"],
            "NEFT": ["NEFT"],
            "RTGS": ["RTGS"],
            "BBPS": ["BBPS"],
            "CARD": ["CARD", "DEBIT CARD", "CREDIT CARD", "POS", "VPA/MMT", "VPA/MMS"],
            "CASH": ["CASH DEP", "CASH WDL"],
            "CHEQUE": ["CHQ", "CHEQUE", "CQ", "CLR"],
            "DIVIDEND": ["DIVIDEND", "DIV"],
            "INTEREST": ["INT PAID", "INT CR"],
            "ECS": ["ECS"],
            "SALARY": ["SALARY"],
            "BILL PAY": ["BILLPAY"],
            "ATM": ["ATM"],
        }
        for method, keywords in payment_methods_keywords.items():
            if any(kw in narration_upper for kw in keywords):
                result["payment_method"] = method
                break

        if not result["upi_id"]:
            upi_id_match = re.search(
                r"[a-z0-9.\-_]+@[a-z]{2,}", narration_upper, re.IGNORECASE
            )
            if upi_id_match:
                result["upi_id"] = upi_id_match.group().strip()
                result["receiver_details"]["vpa"] = result["upi_id"]

        if not result["transaction_reference"]:
            txn_ref_patterns = [
                r"\b(?:RRN|REF|TRF|TXN|UTR|UTR NO|NFS|CMS|ID)\s*[:\.]?\s*([A-Z0-9]{10,25})\b",
                r"\b(YBL|AXI|ICI|KOT|PNB|PYTM|PTM|HDFC|ICICI|YES|SBI)[a-zA-Z0-9]{6,25}\b",
                r"\b(?:\d{10,})\b",
            ]
            for pattern in txn_ref_patterns:
                match = re.search(pattern, narration_upper)
                if match:
                    try:
                        result["transaction_reference"] = match.group(1).strip()
                    except IndexError:
                        result["transaction_reference"] = match.group().strip()
                    break

        receiver_patterns = [
            r"(?:TO|FROM|BY)\s+([A-Z0-9\s.&,-_']{3,}(?:\s(?:A/C|ACC|AC|ACCOUNT|NO)\s*\d+)?)\b",  # Name or Name + A/C
            r"(?:TRANSFER TO|PAYMENT TO)\s+([A-Z\s.&,-_']{3,})",  # Transfer/Payment To Name
            r"CR BY\s+([A-Z\s.&,-_']{3,})",  # Credited by Name
        ]
        for pattern in receiver_patterns:
            match = re.search(pattern, narration_upper)
            if match:
                potential_receiver = match.group(1).strip()
                if re.search(r"\d{6,}", potential_receiver) and not re.search(
                    r"[A-Z]{3,}", potential_receiver
                ):
                    result["receiver_details"]["account"] = potential_receiver
                else:
                    result["receiver_details"]["name"] = potential_receiver
                break

        bank_keywords = [
            "STATE BANK OF INDIA",
            "HDFC BANK",
            "ICICI BANK",
            "AXIS BANK",
            "YES BANK",
            "KOTAK MAHINDRA BANK",
            "PUNJAB NATIONAL BANK",
            "UNION BANK OF INDIA",
            "CANARA BANK",
            "INDIAN BANK",
            "INDUSIND BANK",
            "FEDERAL BANK",
            "RBL BANK",
            "BANDHAN BANK",
            "IDFC FIRST BANK",
            "BANK OF BARODA",
            "UCO BANK",
            "CENTRAL BANK OF INDIA",
            "SBI",
            "HDFC",
            "ICICI",
            "AXIS",
            "KOTAK",
            "PNB",
            "UNION",
            "CANARA",
            "INDUSIND",
            "BOB",
            "UBI",
            "IOB",
            "BOI",
            "CORP",
        ]
        for bank in bank_keywords:
            if bank in narration_upper:
                result["bank_peer"] = bank
                break

        merchants_and_categories = {
            "AMAZON": {"merchant": "AMAZON", "category": "E-COMMERCE"},
            "ZOMATO": {"merchant": "ZOMATO", "category": "FOOD_DELIVERY"},
            "SWIGGY": {"merchant": "SWIGGY", "category": "FOOD_DELIVERY"},
            "GOOGLE PAY": {
                "merchant": "GOOGLE PAY",
                "category": "PAYMENT_APP",
                "payment_gateway": "GOOGLE",
            },
            "PHONEPE": {
                "merchant": "PHONEPE",
                "category": "PAYMENT_APP",
                "payment_gateway": "PHONEPE",
            },
            "PAYTM": {
                "merchant": "PAYTM",
                "category": "PAYMENT_APP",
                "payment_gateway": "PAYTM",
            },
            "RELIANCE": {"merchant": "RELIANCE", "category": "RETAIL"},
            "VODAFONE": {"merchant": "VODAFONE", "category": "TELECOM_BILL"},
            "AIRTEL": {"merchant": "AIRTEL", "category": "TELECOM_BILL"},
            "JIO": {"merchant": "JIO", "category": "TELECOM_BILL"},
            "IRCTC": {"merchant": "IRCTC", "category": "TRAVEL"},
            "UBER": {"merchant": "UBER", "category": "TRANSPORT"},
            "OLA": {"merchant": "OLA", "category": "TRANSPORT"},
            "NETFLIX": {"merchant": "NETFLIX", "category": "SUBSCRIPTION"},
            "SPOTIFY": {"merchant": "SPOTIFY", "category": "SUBSCRIPTION"},
            "CRED": {
                "merchant": "CRED",
                "category": "LOAN_REPAYMENT",
                "payment_gateway": "CRED",
            },
            "ELECTRICITY": {"category": "UTILITY_BILL"},
            "WATER": {"category": "UTILITY_BILL"},
            "GAS": {"category": "UTILITY_BILL"},
            "LOAN EMI": {"category": "LOAN_REPAYMENT"},
            "RENT": {"category": "HOUSING"},
            "SALARY": {"category": "INCOME"},
            "SCHOOL FEES": {"category": "EDUCATION"},
            "INSURANCE": {"category": "INSURANCE"},
            "INVESTMENT": {"category": "INVESTMENT"},
            "SIP": {"category": "INVESTMENT"},
            "MUTUAL FUND": {"category": "INVESTMENT"},
            "FOOD": {"category": "FOOD_EXPENSE"},
            "MEDICAL": {"category": "HEALTH_EXPENSE"},
            "PHARMACY": {"category": "HEALTH_EXPENSE"},
            "CHEMIST": {"category": "HEALTH_EXPENSE"},
            "ECOM": {"category": "E-COMMERCE"},  # Generic e-commerce
            "GROCERY": {"category": "GROCERIES"},
            "FUEL": {"category": "TRANSPORT_FUEL"},
            "TAX": {"category": "TAXES"},
            "LOAN DISB": {"category": "LOAN_DISBURSEMENT"},
        }

        for keyword, details in merchants_and_categories.items():
            if keyword in narration_upper:
                if details.get("merchant") and not result["merchant"]:
                    result["merchant"] = details["merchant"]
                if (
                    details.get("category")
                    and details["category"] not in result["category"]
                ):
                    result["category"].append(details["category"])
                if details.get("payment_gateway") and not result["payment_gateway"]:
                    result["payment_gateway"] = details["payment_gateway"]

        if "REFUND" in narration_upper and "REFUND" not in result["remarks"]:
            result["remarks"].append("REFUND")
        if "TRANSFER" in narration_upper and "TRANSFER" not in result["remarks"]:
            result["remarks"].append("TRANSFER")
        if "DEBITED" in narration_upper and "DEBITED" not in result["remarks"]:
            result["remarks"].append("DEBITED")
        if "CREDITED" in narration_upper and "CREDITED" not in result["remarks"]:
            result["remarks"].append("CREDITED")

        possible_accounts = BankStatementAnalyzer.extract_possible_account_numbers(
            narration_upper
        )
        if possible_accounts:
            result["receiver_details"]["account"] = possible_accounts[0]

        result["category"] = list(
            dict.fromkeys(
                REGEX_TO_CANONICAL.get(c, c) for c in result["category"]
            )
        )

        return result

    @staticmethod
    def extract_possible_account_numbers(description):
        if not description:
            return []

        numbers = set()

        # Pattern 1: Account numbers like 1234 5678 9012
        account_pattern = re.findall(
            r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4,12}\b", description
        )
        for match in account_pattern:
            numbers.add(match.replace(" ", "").replace("-", ""))

        # Pattern 2: Long sequences of 8–20 digits (no formatting)
        long_number_pattern = re.findall(r"\b\d{8,20}\b", description)
        for match in long_number_pattern:
            if len(match) <= 20:
                numbers.add(match)

        # Pattern 3: UPI / REF / TXN references
        upi_ref_pattern = re.findall(
            r"(?:UPI|REF|TXN)[\s\-:]*(\d{8,16})", description, re.IGNORECASE
        )
        numbers.update(upi_ref_pattern)

        # Pattern 4: NEFT / RTGS / IMPS references
        transfer_ref_pattern = re.findall(
            r"(?:NEFT|RTGS|IMPS)[\s\-:]*[A-Z]*(\d{8,16})", description, re.IGNORECASE
        )
        numbers.update(transfer_ref_pattern)

        return sorted(numbers, key=lambda x: -len(x))  # Sort by length descending

    def calculate_confidence_score(self, txn: dict) -> float:
        score = 1.0  # Start with full score, then subtract penalties

        # 1. Transaction Date
        transaction_date = txn.get("transaction_date")
        if not transaction_date or not isinstance(transaction_date, str):
            score -= 0.25

        # 2. Amount
        amount = txn.get("amount")
        if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
            score -= 0.25

        # 3. Narration
        narration = txn.get("narration")
        if not narration:
            score -= 0.15
        elif isinstance(narration, str) and len(narration.strip()) < 5:
            score -= 0.05  # weak/short narration

        # 4. Transaction Type
        if not txn.get("transaction_type"):
            score -= 0.10

        # 5. Receiver Details
        receiver = txn.get("receiver_details", {})
        if (
            not receiver.get("name")
            and not receiver.get("account")
            and not receiver.get("vpa")
        ):
            score -= 0.10

        # 6. Balance Field
        if txn.get("balance") is None:
            score -= 0.05

        # Clamp score between 0 and 1
        final_score = max(0.0, min(round(score, 2), 1.0))
        return final_score


class TransactionPatternTrainer:
    def __init__(self):
        pass

    def analyze(self, transactions: list) -> dict:
        merchants = defaultdict(list)

        for txn in transactions:
            merchant = txn.get("merchant")
            if not merchant:
                receiver_name = txn.get("receiver_details", {}).get("name") or ""
                if receiver_name and re.search(r"[A-Za-z]{2,}", receiver_name):
                    merchant = receiver_name.strip()
                else:
                    merchant = "UNKNOWN"
            merchants[merchant].append(txn)

        insights = {}
        for m, txns in merchants.items():
            amounts = [
                t.get("amount")
                for t in txns
                if isinstance(t.get("amount"), (int, float))
            ]
            dates = [
                t.get("transaction_date") for t in txns if t.get("transaction_date")
            ]

            parsed_dates = []
            for d in dates:
                try:
                    pd_dt = pd.to_datetime(d, errors="coerce")
                    if pd.notna(pd_dt):
                        parsed_dates.append(pd_dt)
                except Exception:
                    continue

            count = len(txns)
            avg = float(pd.Series(amounts).mean()) if amounts else None
            median = float(pd.Series(amounts).median()) if amounts else None
            std = (
                float(pd.Series(amounts).std())
                if amounts and len(amounts) > 1
                else None
            )

            first = min(parsed_dates).strftime("%Y-%m-%d") if parsed_dates else None
            last = max(parsed_dates).strftime("%Y-%m-%d") if parsed_dates else None

            days = [p.day for p in parsed_dates]
            common_days = sorted({d for d in days if days.count(d) > 1})

            insights[m] = {
                "count": count,
                "avg_amount": round(avg, 2) if avg is not None else None,
                "median_amount": round(median, 2) if median is not None else None,
                "std_amount": round(std, 2) if std is not None else None,
                "first_seen": first,
                "last_seen": last,
                "common_days": common_days,
            }

        return insights


# NOTE: EnhancedNarrationAnalyzer, TransactionPatternLearner, BalanceValidator,
# and EnhancedConfidenceScorer were removed — all were incomplete stubs never
# called anywhere. Track planned ML/AI features as separate tickets.
