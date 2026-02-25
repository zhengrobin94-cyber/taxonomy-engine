"""
Module: main
Description: Entrypoint for the FastAPI application
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, status

from app.api.routes.chunk import router as chunk_router
from app.api.routes.concept import router as concept_router
from app.api.routes.taxonomy import router as taxonomy_router
from app.settings import settings
from app.utils import init_logging

init_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup events
    logger.info("Starting up the application...")
    yield
    # Shutdown events
    logger.info("Shutting down the application...")


app = FastAPI(
    title="Taxonomy Engine API",
    summary="Extract concepts from standards documents and update taxonomy.",
    description="This API aims to __suggest an updated version of an existing concepts taxonomy for a given domain__ by,\n1. generating chunks from standards related to the domain of interest > _Chunking_;\n2. extracting concepts from these chunks > _Extracting Concept_;\n3. updating the existing taxonomy by introducing the extracted concepts > _Updating Taxonomy_.\n\nAs such, this API is organized around those 3 steps.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(chunk_router)
app.include_router(concept_router)
app.include_router(taxonomy_router)


@app.get("/health", summary="Health Check", status_code=status.HTTP_200_OK)
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=settings.reload,
        log_config=settings.logging_config,
    )
