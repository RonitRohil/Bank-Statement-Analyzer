from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def health_check():
    return {"status": "ok", "service": "bank-statement-analyzer-v2"}
