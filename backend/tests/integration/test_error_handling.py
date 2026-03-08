from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import RAGPipelineError
from app.main import app


@pytest.mark.asyncio
async def test_corpus_exception_returns_structured_error():
    with patch("app.api.dependencies._rag_pipeline") as mock_pipeline:
        mock_pipeline.query = AsyncMock(
            side_effect=RAGPipelineError("Something went wrong in the pipeline")
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/query", json={"question": "What is DP?"})

    assert response.status_code == 500
    data = response.json()
    assert data["error_type"] == "RAGPipelineError"
    assert "pipeline" in data["detail"].lower()
