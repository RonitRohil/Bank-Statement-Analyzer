import hashlib
import json
from typing import Optional

from sqlmodel import Session, select

from app.db.models import StatementDB, TransactionDB


def hash_file(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def find_statement_by_hash(session: Session, file_hash: str) -> Optional[StatementDB]:
    return session.exec(
        select(StatementDB).where(StatementDB.file_hash == file_hash)
    ).first()


def save_statement(
    session: Session, file_hash: str, filename: str, result: dict
) -> StatementDB:
    account_info = result.get("result", {}).get("account_info", {})
    period = account_info.get("statement_period") or {}
    summary = result.get("result", {}).get("confidence_summary", {})

    stmt = StatementDB(
        file_hash=file_hash,
        original_filename=filename,
        account_number=account_info.get("account_number"),
        bank_name=account_info.get("bank_name"),
        account_holder=account_info.get("account_holder"),
        period_from=period.get("from"),
        period_to=period.get("to"),
        confidence_overall=summary.get("overall_score"),
    )
    session.add(stmt)
    session.flush()  # populate stmt.id without committing

    for txn in result.get("result", {}).get("transactions", []):
        row = TransactionDB(
            statement_id=stmt.id,
            transaction_date=txn.get("transaction_date"),
            amount=txn.get("amount"),
            transaction_type=txn.get("transaction_type"),
            narration=txn.get("narration"),
            balance=txn.get("balance"),
            payment_method=txn.get("payment_method"),
            merchant=txn.get("merchant"),
            category=json.dumps(txn.get("category") or []),
            payment_gateway=txn.get("payment_gateway"),
            transaction_reference=txn.get("transaction_reference"),
            confidence_score=txn.get("confidence_score"),
            llm_enriched=txn.get("llm_enriched", False),
        )
        session.add(row)

    session.commit()
    session.refresh(stmt)
    return stmt
