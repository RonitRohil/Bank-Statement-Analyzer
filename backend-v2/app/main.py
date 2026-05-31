import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.routers import health

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bank Statement Analyzer API v2",
    description="Parses and analyzes bank statements (PDF, Excel, CSV) with transaction enrichment.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)


@app.on_event("startup")
async def on_startup():
    logger.info("Bank Statement Analyzer v2 started on port 8000")
