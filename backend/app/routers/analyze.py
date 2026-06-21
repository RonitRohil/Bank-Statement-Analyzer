import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.config.settings import settings
from app.db.crud import find_statement_by_hash, hash_file, save_statement
from app.db.database import get_session
from app.models.analyzer import BankStatementAnalyzer, TransactionPatternTrainer
from app.models.schemas import AnalyzeResponse
from app.services.insights import generate_insights
from app.services.llm_enricher import enrich_with_llm

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls"}
MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024


@router.post("/api/analyze/bank/statement", response_model=AnalyzeResponse)
async def analyze_statement(
    file: UploadFile = File(...),
    persist: bool = False,
    session: Session = Depends(get_session),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Allowed: PDF, CSV, XLSX, XLS.",
        )

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_size_mb} MB limit.",
        )

    if persist:
        file_hash = hash_file(content)
        existing = find_statement_by_hash(session, file_hash)
        if existing:
            return JSONResponse(
                content={
                    "cached": True,
                    "statement_id": existing.id,
                    "message": "Statement already analyzed",
                }
            )

    unique_name = f"{uuid.uuid4().hex}{suffix}"
    file_path = UPLOAD_DIR / unique_name

    try:
        file_path.write_bytes(content)
        result = await asyncio.to_thread(
            lambda: BankStatementAnalyzer(str(file_path)).extract_transactions()
        )
        http_status = result.get("status_code", 200)
        if http_status != 200:
            raise HTTPException(
                status_code=http_status, detail=result.get("message", "Analysis failed")
            )

        if result.get("result", {}).get("transactions"):
            enriched = await enrich_with_llm(result["result"]["transactions"])
            result["result"]["transactions"] = enriched
            result["result"]["merchant_insights"] = TransactionPatternTrainer().analyze(
                enriched
            )
            result["result"]["insights"] = generate_insights(
                enriched, result["result"]["merchant_insights"]
            )

        if persist:
            save_statement(session, file_hash, file.filename, result)

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if file_path.exists():
            file_path.unlink()
