from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    with patch("app.api.dependencies._neo4j_client") as mock_neo4j, \
         patch("app.api.dependencies._embedding_service") as mock_embeddings:

        mock_neo4j.health_check = AsyncMock(return_value=True)
        mock_embeddings.redis_client = MagicMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        assert "status" in response.json()


@pytest.mark.asyncio
async def test_root_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json()["message"] == "Corpus RAG Backend"
