from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db.database import get_session
from app.db.models import StatementDB

router = APIRouter()


@router.get("/api/statements")
def list_statements(session: Session = Depends(get_session)):
    statements = session.exec(
        select(StatementDB).order_by(StatementDB.uploaded_at.desc())
    ).all()
    return {"statements": [s.model_dump() for s in statements]}
