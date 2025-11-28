"""Unit tests for graph endpoint."""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.models.schemas import ConceptGraph, ConceptNode, ConceptEdge


@pytest.mark.asyncio
async def test_get_concept_graph_success():
    """Test successful graph retrieval."""
    mock_graph = ConceptGraph(
        nodes=[
            ConceptNode(name="Dynamic Programming", node_type="concept"),
            ConceptNode(name="Memoization", node_type="concept"),
        ],
        edges=[
            ConceptEdge(
                source="Dynamic Programming",
                target="Memoization",
                edge_type="RELATES_TO",
                weight=1.0,
            )
        ],
    )

    with patch("app.api.dependencies._neo4j_client") as mock_neo4j:
        mock_neo4j.get_concept_graph = AsyncMock(return_value=mock_graph)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/graph/dynamic%20programming?depth=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1


@pytest.mark.asyncio
async def test_get_concept_graph_not_found():
    """Test graph retrieval for non-existent concept."""
    empty_graph = ConceptGraph(nodes=[], edges=[])

    with patch("app.api.dependencies._neo4j_client") as mock_neo4j:
        mock_neo4j.get_concept_graph = AsyncMock(return_value=empty_graph)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/graph/nonexistent?depth=2")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
