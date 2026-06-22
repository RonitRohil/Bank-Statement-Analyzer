import logging
import os
import re

import pandas as pd

from collections import defaultdict

from app.parsers.excel_parser import (
    clean_column_name,
    deduplicate_transactions,
    detect_header_row,
    find_column,
    process_excel_csv,
)
from app.parsers.pdf_parser import looks_like_header, process_pdf_transactions

logger = logging.getLogger(__name__)


class BankStatementAnalyzer:

    def __init__(self, file_path):
        self.file_path = file_path

    @staticmethod
    def _looks_like_header(row):
        return looks_like_header(row)

    def _deduplicate_transactions(self, transactions: list[dict]) -> list[dict]:
        before = len(transactions)
        deduped = deduplicate_transactions(transactions)
        dropped = before - len(deduped)
        if dropped > 0:
            logger.info("[DEDUP] Removed %d duplicate transaction(s)", dropped)
        return deduped

    def _get_statement_range_from_df(self, df):
        date_col = find_column(
            ["date", "txn_date", "transaction_date", "value_date"], df.columns
        )
        if date_col:
            dates = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
            valid_dates = dates.dropna()
            if not valid_dates.empty:
                return {
                    "from": valid_dates.min().strftime("%Y-%m-%d"),
                    "to": valid_dates.max().strftime("%Y-%m-%d"),
                }
        logger.debug("Could not determine statement date range.")
        return {}

    def _extract_metadata_from_df(self, raw_df, max_lines=30):
        try:
            lines = (
                raw_df.iloc[:max_lines].fillna("").astype(str).values.flatten().tolist()
            )
            text_blob = " ".join([line.strip() for line in lines if line.strip()])
            metadata = self._extract_metadata_from_text(text_blob)

            try:
                header_row_index = detect_header_row(raw_df)
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
                    clean_column_name(col) for col in df_for_dates.columns
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

        patterns = {
            "account_number": [
                r"(?:account|a/c|acct)\s*(?:no|num|number)?\s*[:\.]?\s*(\d{9,18})\b",
                r"\b(\d{3,5}(?:-\d{2,5}){2,})\b",
                r"\b(?:[Ii]nd[Oo]\s*)?(\d{11})\b",
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
                r"\b([A-Z]{4}0[A-Z0-9]{6})\b",
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
            r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b",
            r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\b",
            r"\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b",
        ]

        all_found_dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text_blob, re.IGNORECASE)
            for d_str in matches:
                try:
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

    def _process_excel_csv(self):
        result = process_excel_csv(self.file_path, self._extract_metadata_from_df)
        if result.get("result") is not None and "transactions" in result.get("result", {}):
            result["result"]["merchant_insights"] = TransactionPatternTrainer().analyze(
                result["result"]["transactions"]
            )
        return result

    def _process_pdf_transactions(self):
        result = process_pdf_transactions(
            self.file_path, self._extract_metadata_from_text
        )
        if result.get("result") is not None and "transactions" in result.get("result", {}):
            result["result"]["merchant_insights"] = TransactionPatternTrainer().analyze(
                result["result"]["transactions"]
            )
        return result

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
