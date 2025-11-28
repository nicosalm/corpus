"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.embeddings import EmbeddingService
from app.services.neo4j_client import Neo4jClient
from app.services.pdf_processor import PDFProcessor


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    from app.core.config import Settings

    return Settings(
        anthropic_api_key="test_anthropic_key",
        openai_api_key="test_openai_key",
        fish_audio_api_key="test_fish_key",
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        redis_url="redis://localhost:6379",
        environment="test",
        log_level="DEBUG",
    )


@pytest.fixture
def pdf_processor():
    """Create PDF processor instance."""
    return PDFProcessor()


@pytest.fixture
async def mock_embedding_service():
    """Mock embedding service."""
    service = AsyncMock(spec=EmbeddingService)
    service.embed_text.return_value = [0.1] * 1536  # Mock embedding
    service.embed_query.return_value = [0.1] * 1536
    return service


@pytest.fixture
async def mock_neo4j_client():
    """Mock Neo4j client."""
    client = AsyncMock(spec=Neo4jClient)
    client.health_check.return_value = True
    return client
