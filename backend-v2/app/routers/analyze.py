import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config.settings import settings
from app.models.analyzer import BankStatementAnalyzer
from app.models.schemas import AnalyzeResponse

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls"}
MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024


@router.post("/api/analyze/bank/statement", response_model=AnalyzeResponse)
async def analyze_statement(file: UploadFile = File(...)):
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

    unique_name = f"{uuid.uuid4().hex}{suffix}"
    file_path = UPLOAD_DIR / unique_name

    try:
        file_path.write_bytes(content)
        result = await asyncio.to_thread(
            lambda: BankStatementAnalyzer(str(file_path)).extract_transactions()
        )
        http_status = result.get("status_code", 200)
        if http_status != 200:
            raise HTTPException(status_code=http_status, detail=result.get("message", "Analysis failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if file_path.exists():
            file_path.unlink()
