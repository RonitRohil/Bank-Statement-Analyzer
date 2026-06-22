import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.db.crud import fingerprint_transaction, save_correction
from app.db.database import get_session
from app.services.categories import CANONICAL_CATEGORIES

router = APIRouter()
logger = logging.getLogger(__name__)


class CorrectionRequest(BaseModel):
    transaction_date: str
    amount: float
    narration: str
    corrected_category: str
    corrected_merchant: str | None = None


class CorrectionResponse(BaseModel):
    fingerprint: str
    corrected_category: str
    corrected_merchant: str | None


@router.post("/api/corrections", response_model=CorrectionResponse, status_code=201)
def submit_correction(
    req: CorrectionRequest, session: Session = Depends(get_session)
):
    if req.corrected_category not in CANONICAL_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown category '{req.corrected_category}'. Valid values: {CANONICAL_CATEGORIES}",
        )
    fp = fingerprint_transaction(req.transaction_date, req.amount, req.narration)
    save_correction(session, fp, req.corrected_category, req.corrected_merchant)
    return CorrectionResponse(
        fingerprint=fp,
        corrected_category=req.corrected_category,
        corrected_merchant=req.corrected_merchant,
    )
