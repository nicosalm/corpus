"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import dependencies
from app.api.routes import graph, health, ingest, query
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.services.concept_extractor import ConceptExtractor
from app.services.embeddings import EmbeddingService
from app.services.neo4j_client import Neo4jClient
from app.services.rag_pipeline import RAGPipeline

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    settings = get_settings()
    logger.info("application_starting", environment=settings.environment)

    # Initialize services
    embedding_service = EmbeddingService()
    neo4j_client = Neo4jClient()
    concept_extractor = ConceptExtractor()
    rag_pipeline = RAGPipeline(
        embedding_service=embedding_service,
        neo4j_client=neo4j_client,
    )

    # Connect to external services
    try:
        await embedding_service.connect_redis()
        await neo4j_client.connect()

        # Initialize dependency injection
        dependencies.initialize_services(
            embedding_service=embedding_service,
            neo4j_client=neo4j_client,
            rag_pipeline=rag_pipeline,
            concept_extractor=concept_extractor,
        )

        logger.info("application_started")

    except Exception as e:
        logger.error("application_startup_failed", error=str(e))
        raise

    yield

    # Cleanup on shutdown
    logger.info("application_shutting_down")
    await embedding_service.close_redis()
    await neo4j_client.close()
    logger.info("application_stopped")


# Create FastAPI app
app = FastAPI(
    title="Corpus RAG Backend",
    description="Knowledge graph RAG system for personal notes",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(query.router)
app.include_router(ingest.router)
app.include_router(graph.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Corpus RAG Backend",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
    )
