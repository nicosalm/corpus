from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.api.dependencies import get_embedding_service, get_neo4j_client
from app.models.schemas import HealthResponse
from app.services.embeddings import EmbeddingService
from app.services.neo4j_client import Neo4jClient

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health_check(
    neo4j: Neo4jClient = Depends(get_neo4j_client),
    embeddings: EmbeddingService = Depends(get_embedding_service),
) -> HealthResponse:
    neo4j_ok = await neo4j.health_check()
    redis_ok = embeddings.redis_client is not None
    status = "healthy" if (neo4j_ok and redis_ok) else "degraded"

    return HealthResponse(
        status=status,
        neo4j_connected=neo4j_ok,
        redis_connected=redis_ok,
        timestamp=datetime.now(UTC),
    )
