from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_neo4j_client
from app.core.logging import get_logger
from app.models.schemas import ConceptGraph
from app.services.neo4j_client import Neo4jClient

logger = get_logger(__name__)

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/{concept}", response_model=ConceptGraph)
async def get_concept_graph(
    concept: str,
    depth: int = Query(default=2, ge=1, le=4),
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> ConceptGraph:
    logger.info("graph_query", concept=concept, depth=depth)

    graph = await neo4j.get_concept_graph(concept_name=concept, depth=depth)

    if not graph.nodes:
        raise HTTPException(
            status_code=404,
            detail=f"Concept '{concept}' not found in knowledge graph",
        )

    logger.info("graph_retrieved", concept=concept, nodes=len(graph.nodes), edges=len(graph.edges))
    return graph
