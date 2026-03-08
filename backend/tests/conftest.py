import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("COHERE_API_KEY", "test_key")
os.environ.setdefault("NEO4J_PASSWORD", "test_password")

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.concept_extractor import ConceptExtractor
from app.services.embeddings import EmbeddingService
from app.services.neo4j_client import Neo4jClient
from app.services.pdf_processor import PDFProcessor
from app.services.rag_pipeline import RAGPipeline


@pytest.fixture
def pdf_processor():
    return PDFProcessor()


@pytest.fixture
def mock_embedding_service():
    service = AsyncMock(spec=EmbeddingService)
    service.embed_text.return_value = ([0.1] * 1536, 10)
    service.embed_query.return_value = ([0.1] * 1536, 10)
    service.embed_chunks.return_value = ([], 0)
    service.redis_client = MagicMock()
    return service


@pytest.fixture
def mock_neo4j_client():
    client = AsyncMock(spec=Neo4jClient)
    client.health_check.return_value = True
    return client


@pytest.fixture
def mock_concept_extractor():
    extractor = AsyncMock(spec=ConceptExtractor)
    extractor.extract_concepts.return_value = []
    extractor.extract_batch.return_value = {}
    return extractor


@pytest.fixture
def mock_rag_pipeline(mock_embedding_service, mock_neo4j_client):
    return AsyncMock(spec=RAGPipeline)
