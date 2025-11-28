"""Graph exploration endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.logging import get_logger
from app.models.schemas import ConceptGraph
from app.services.neo4j_client import Neo4jClient
from app.api.dependencies import get_neo4j_client

logger = get_logger(__name__)

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/{concept}", response_model=ConceptGraph)
async def get_concept_graph(
    concept: str,
    depth: int = Query(default=2, ge=1, le=4, description="Graph traversal depth"),
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> ConceptGraph:
    """
    Get the knowledge graph neighborhood around a concept.

    Args:
        concept: Central concept name
        depth: How many relationship hops to traverse (1-4)
        neo4j: Neo4j client (injected)

    Returns:
        Graph structure with nodes and edges
    """
    try:
        logger.info("graph_query", concept=concept, depth=depth)

        graph = await neo4j.get_concept_graph(
            concept_name=concept,
            depth=depth,
        )

        if not graph.nodes:
            logger.warning("concept_not_found", concept=concept)
            raise HTTPException(
                status_code=404,
                detail=f"Concept '{concept}' not found in knowledge graph",
            )

        logger.info(
            "graph_retrieved",
            concept=concept,
            nodes=len(graph.nodes),
            edges=len(graph.edges),
        )

        return graph

    except HTTPException:
        raise
    except Exception as e:
        logger.error("graph_query_failed", concept=concept, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
