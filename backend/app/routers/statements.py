from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db.database import get_session
from app.db.models import StatementDB, TransactionDB

router = APIRouter()


@router.get("/api/statements")
def list_statements(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
    session: Session = Depends(get_session),
):
    statements = session.exec(
        select(StatementDB)
        .order_by(StatementDB.uploaded_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "statements": [s.model_dump() for s in statements],
        "limit": limit,
        "offset": offset,
    }


@router.get("/api/statements/{statement_id}/transactions")
def get_statement_transactions(
    statement_id: int,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    session: Session = Depends(get_session),
):
    """Return all stored transactions for a specific statement."""
    txns = session.exec(
        select(TransactionDB)
        .where(TransactionDB.statement_id == statement_id)
        .offset(offset)
        .limit(limit)
    ).all()
    if not txns:
        raise HTTPException(
            status_code=404,
            detail=f"No transactions found for statement {statement_id}",
        )
    return {
        "statement_id": statement_id,
        "transactions": [t.model_dump() for t in txns],
    }
