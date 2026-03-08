from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import dependencies
from app.api.routes import graph, health, ingest, query
from app.core.config import get_settings
from app.core.exceptions import CorpusError
from app.core.logging import get_logger, setup_logging
from app.services.concept_extractor import ConceptExtractor
from app.services.embeddings import EmbeddingService
from app.services.neo4j_client import Neo4jClient
from app.services.rag_pipeline import RAGPipeline

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info("application_starting", environment=settings.environment)

    embedding_service = EmbeddingService()
    neo4j_client = Neo4jClient()
    concept_extractor = ConceptExtractor()
    rag_pipeline = RAGPipeline(
        embedding_service=embedding_service,
        neo4j_client=neo4j_client,
    )

    try:
        await embedding_service.connect_redis()
        await neo4j_client.connect()
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

    logger.info("application_shutting_down")
    await embedding_service.close_redis()
    await neo4j_client.close()
    logger.info("application_stopped")


app = FastAPI(
    title="Corpus RAG Backend",
    description="Knowledge graph RAG system for personal notes",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_EXCEPTION_STATUS_MAP = {
    "PDFProcessingError": 400,
    "ValidationError": 422,
    "EmbeddingError": 502,
    "Neo4jError": 503,
    "RAGPipelineError": 500,
    "ChunkingError": 500,
}


@app.exception_handler(CorpusError)
async def corpus_exception_handler(request: Request, exc: CorpusError) -> JSONResponse:
    error_type = type(exc).__name__
    status = _EXCEPTION_STATUS_MAP.get(error_type, 500)
    logger.error(
        "unhandled_domain_error",
        error_type=error_type,
        error=exc.message,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=status,
        content={"detail": exc.message, "error_type": error_type},
    )


app.include_router(health.router)
app.include_router(query.router)
app.include_router(ingest.router)
app.include_router(graph.router)


@app.get("/")
async def root() -> dict[str, str]:
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
