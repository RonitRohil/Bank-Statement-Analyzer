import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.routers import health, analyze, summary

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Bank Statement Analyzer v2 started on port 8000")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.get(f"{settings.ollama_base_url}/v1/models")
        logger.info("[startup] Ollama reachable at %s", settings.ollama_base_url)
    except Exception:
        logger.warning(
            "[startup] Ollama not reachable at %s — LLM enrichment will be skipped",
            settings.ollama_base_url,
        )
    yield


app = FastAPI(
    title="Bank Statement Analyzer API v2",
    description="Parses and analyzes bank statements (PDF, Excel, CSV) with transaction enrichment.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(summary.router)
