"""Dependency injection for FastAPI routes."""

from typing import AsyncGenerator

from app.services.concept_extractor import ConceptExtractor
from app.services.embeddings import EmbeddingService
from app.services.neo4j_client import Neo4jClient
from app.services.rag_pipeline import RAGPipeline

# Global service instances (initialized in main.py)
_embedding_service: EmbeddingService | None = None
_neo4j_client: Neo4jClient | None = None
_rag_pipeline: RAGPipeline | None = None
_concept_extractor: ConceptExtractor | None = None


def initialize_services(
    embedding_service: EmbeddingService,
    neo4j_client: Neo4jClient,
    rag_pipeline: RAGPipeline,
    concept_extractor: ConceptExtractor,
) -> None:
    """Initialize global service instances."""
    global _embedding_service, _neo4j_client, _rag_pipeline, _concept_extractor
    _embedding_service = embedding_service
    _neo4j_client = neo4j_client
    _rag_pipeline = rag_pipeline
    _concept_extractor = concept_extractor


async def get_embedding_service() -> EmbeddingService:
    """Get embedding service instance."""
    if _embedding_service is None:
        raise RuntimeError("EmbeddingService not initialized")
    return _embedding_service


async def get_neo4j_client() -> Neo4jClient:
    """Get Neo4j client instance."""
    if _neo4j_client is None:
        raise RuntimeError("Neo4jClient not initialized")
    return _neo4j_client


async def get_rag_pipeline() -> RAGPipeline:
    """Get RAG pipeline instance."""
    if _rag_pipeline is None:
        raise RuntimeError("RAGPipeline not initialized")
    return _rag_pipeline


async def get_concept_extractor() -> ConceptExtractor:
    """Get concept extractor instance."""
    if _concept_extractor is None:
        raise RuntimeError("ConceptExtractor not initialized")
    return _concept_extractor
