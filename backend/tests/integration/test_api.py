"""Integration tests for API endpoints."""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    with patch("app.api.dependencies._neo4j_client") as mock_neo4j, \
         patch("app.api.dependencies._embedding_service") as mock_embeddings:

        mock_neo4j.health_check = AsyncMock(return_value=True)
        mock_embeddings.redis_client = MagicMock()

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["message"] == "Corpus RAG Backend"
