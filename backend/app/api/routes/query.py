"""Query endpoint for RAG pipeline."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.logging import get_logger
from app.models.schemas import QueryRequest, QueryResponse
from app.services.rag_pipeline import RAGPipeline
from app.api.dependencies import get_rag_pipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
) -> QueryResponse:
    """
    Query the knowledge base using RAG.

    Args:
        request: Query request with question and parameters
        pipeline: RAG pipeline instance (injected)

    Returns:
        Answer with retrieved chunks and optional concept graph
    """
    try:
        logger.info("api_query_received", question=request.question)

        response = await pipeline.query(
            question=request.question,
            max_chunks=request.max_chunks,
            include_graph=request.include_graph,
        )

        return response

    except Exception as e:
        logger.error("api_query_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
