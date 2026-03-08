from fastapi import APIRouter, Depends

from app.api.dependencies import get_rag_pipeline
from app.core.logging import get_logger
from app.models.schemas import QueryRequest, QueryResponse
from app.services.rag_pipeline import RAGPipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
) -> QueryResponse:
    logger.info("api_query_received", question=request.question)
    return await pipeline.query(
        question=request.question,
        max_chunks=request.max_chunks,
        include_graph=request.include_graph,
    )
