import hashlib
import json
from collections import defaultdict
from typing import Optional

from sqlmodel import Session, select

from app.db.models import CorrectionDB, StatementDB, TransactionDB


def hash_file(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def fingerprint_transaction(transaction_date: str, amount: float, narration: str) -> str:
    """
    Compute the correction fingerprint for a transaction.
    Format: SHA-256 of "{transaction_date}:{amount}:{narration[:100]}"
    Normalize narration: strip whitespace, lowercase.
    This MUST match any client-side fingerprint computation.
    Any change to this function MUST be backward-compatible or stored corrections will break.
    """
    norm_narration = (narration or "").strip().lower()[:100]
    raw = f"{transaction_date}:{amount}:{norm_narration}"
    return hashlib.sha256(raw.encode()).hexdigest()


def save_correction(
    session: Session,
    fingerprint: str,
    corrected_category: str,
    corrected_merchant: str | None = None,
) -> CorrectionDB:
    """Upsert a correction keyed by fingerprint."""
    existing = session.exec(
        select(CorrectionDB).where(CorrectionDB.fingerprint == fingerprint)
    ).first()
    if existing:
        existing.corrected_category = corrected_category
        if corrected_merchant is not None:
            existing.corrected_merchant = corrected_merchant
        session.add(existing)
        session.commit()
        return existing
    else:
        correction = CorrectionDB(
            fingerprint=fingerprint,
            corrected_category=corrected_category,
            corrected_merchant=corrected_merchant,
        )
        session.add(correction)
        session.commit()
        return correction


def get_correction(session: Session, fingerprint: str) -> Optional[CorrectionDB]:
    """Look up a stored correction by fingerprint. Returns None if not found."""
    return session.exec(
        select(CorrectionDB).where(CorrectionDB.fingerprint == fingerprint)
    ).first()


def find_statement_by_hash(session: Session, file_hash: str) -> Optional[StatementDB]:
    return session.exec(
        select(StatementDB).where(StatementDB.file_hash == file_hash)
    ).first()


def save_statement(
    session: Session,
    file_hash: str,
    filename: str,
    result: dict,
    recurring_candidates: list | None = None,
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
        # Frozen at upload time. Re-upload the statement to refresh recurring detection.
        # This is intentional: stores the detection result as it was at upload, independent of future threshold changes.
        recurring_candidates_json=json.dumps(recurring_candidates or []),
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


def get_monthly_summary(account_number: str, session: Session) -> list[dict]:
    """Aggregate transactions by calendar month for a given account number."""
    statements = session.exec(
        select(StatementDB)
        .where(StatementDB.account_number == account_number)
        .order_by(StatementDB.period_from.asc())
    ).all()

    if not statements:
        return []

    monthly: dict[str, dict] = {}

    for stmt in statements:
        txns = session.exec(
            select(TransactionDB)
            .where(TransactionDB.statement_id == stmt.id)
            .limit(5000)  # cap: prevents memory spike on very large statements
        ).all()

        for txn in txns:
            if not txn.transaction_date:
                continue
            month_key = txn.transaction_date[:7]  # "YYYY-MM"
            if month_key not in monthly:
                monthly[month_key] = {
                    "month": month_key,
                    "income": 0.0,
                    "expenses": 0.0,
                    "net": 0.0,
                    "transaction_count": 0,
                    "category_totals": defaultdict(float),
                }
            m = monthly[month_key]
            amount = abs(txn.amount or 0.0)
            txn_type = (txn.transaction_type or "").upper()
            m["transaction_count"] += 1
            if txn_type in ("CREDIT", "CR"):
                m["income"] += amount
            else:
                m["expenses"] += amount
                cats = json.loads(txn.category or "[]")
                for cat in cats:
                    m["category_totals"][cat] += amount

    result = []
    months_sorted = sorted(monthly.keys())
    for i, month_key in enumerate(months_sorted):
        m = monthly[month_key]
        net = round(m["income"] - m["expenses"], 2)
        top_cat = (
            max(m["category_totals"], key=m["category_totals"].get)
            if m["category_totals"]
            else None
        )
        delta = None
        if i > 0:
            prev_exp = monthly[months_sorted[i - 1]]["expenses"]
            if prev_exp > 0:
                delta = round(((m["expenses"] - prev_exp) / prev_exp) * 100, 1)
        result.append({
            "month": month_key,
            "income": round(m["income"], 2),
            "expenses": round(m["expenses"], 2),
            "net": net,
            "transaction_count": m["transaction_count"],
            "top_category": top_cat,
            "delta_expenses_pct": delta,
        })

    return result


def get_cross_statement_recurring(account_number: str, session: Session) -> list[dict]:
    """
    Returns merchants that appear as recurring_candidates in ≥2 of the last 3
    stored statements for the given account number.
    """
    stmts = session.exec(
        select(StatementDB)
        .where(StatementDB.account_number == account_number)
        .order_by(StatementDB.uploaded_at.desc())
        .limit(3)
    ).all()

    if len(stmts) < 2:
        return []

    merchant_appearances: dict[str, list[dict]] = {}
    for stmt in stmts:
        candidates = json.loads(stmt.recurring_candidates_json or "[]")
        for c in candidates:
            m = c.get("merchant")
            if m:
                merchant_appearances.setdefault(m, []).append(c)

    confirmed = []
    for merchant, appearances in merchant_appearances.items():
        if len(appearances) >= 2:
            avg_amount = sum(a.get("avg_amount", 0) for a in appearances) / len(appearances)
            confirmed.append({
                "merchant": merchant,
                "statement_count": len(appearances),
                "avg_amount": round(avg_amount, 2),
                "last_seen": appearances[0].get("last_seen"),
            })

    return sorted(confirmed, key=lambda x: x["statement_count"], reverse=True)
