from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.db.database import get_session
from app.services.qa_engine import answer_question

router = APIRouter()


class QARequest(BaseModel):
    question: str
    account_number: str | None = None


class QAResponse(BaseModel):
    answer: str
    tool_used: str
    data_points: int


@router.post("/api/qa/ask", response_model=QAResponse)
async def ask_question(req: QARequest, session: Session = Depends(get_session)):
    """Answer a natural-language question about stored transaction history."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    result = await answer_question(req.question, req.account_number, session)
    return QAResponse(**result)
