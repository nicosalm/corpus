from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import ChunkMetadata, DocumentChunk
from app.services.rag_pipeline import RAGPipeline


def _make_chunks(n: int = 3) -> list[DocumentChunk]:
    return [
        DocumentChunk(
            content=f"Chunk {i} content about algorithms",
            metadata=ChunkMetadata(
                chunk_id=f"chunk_{i}",
                course="CS331",
                lecture="Lecture 5",
                page_num=i,
                relevance_score=0.9 - (i * 0.1),
            ),
        )
        for i in range(n)
    ]


def _make_pipeline(**overrides):
    with patch.object(RAGPipeline, "__init__", lambda self, **kw: None):
        pipeline = RAGPipeline()
        pipeline.settings = MagicMock()
        pipeline.settings.max_chunks_retrieved = 20
        pipeline.settings.relevance_threshold = 0.5
        for key, value in overrides.items():
            setattr(pipeline, key, value)
        return pipeline


@pytest.mark.asyncio
async def test_query_full_pipeline():
    chunks = _make_chunks(3)
    pipeline = _make_pipeline(
        embedding_service=AsyncMock(**{"embed_query.return_value": ([0.1] * 1536, 10)}),
        neo4j_client=AsyncMock(**{"vector_search.return_value": chunks}),
    )
    pipeline._rerank_chunks = AsyncMock(return_value=chunks[:2])
    pipeline._generate_answer = AsyncMock(return_value=("The answer is 42.", 500, 100))
    pipeline._build_concept_graph = AsyncMock(return_value=None)
    pipeline._calculate_cost = MagicMock(return_value=0.05)

    result = await pipeline.query("What is DP?", max_chunks=2, include_graph=True)

    assert result.answer == "The answer is 42."
    assert len(result.chunks) == 2
    assert result.cost_cents == 0.05
    assert result.processing_time_ms > 0


@pytest.mark.asyncio
async def test_rerank_with_cohere():
    pipeline = _make_pipeline()

    mock_result_0 = MagicMock(index=2, relevance_score=0.98)
    mock_result_1 = MagicMock(index=0, relevance_score=0.75)
    pipeline.cohere_client = AsyncMock()
    pipeline.cohere_client.rerank.return_value = MagicMock(results=[mock_result_0, mock_result_1])

    chunks = _make_chunks(3)
    result = await pipeline._rerank_chunks("test query", chunks, top_k=2)

    assert len(result) == 2
    assert result[0].metadata.chunk_id == "chunk_2"
    assert result[0].metadata.relevance_score == 0.98
    assert result[1].metadata.chunk_id == "chunk_0"


@pytest.mark.asyncio
async def test_rerank_fallback_on_cohere_error():
    pipeline = _make_pipeline()
    pipeline.cohere_client = AsyncMock()
    pipeline.cohere_client.rerank.side_effect = RuntimeError("Cohere down")

    result = await pipeline._rerank_chunks("test query", _make_chunks(3), top_k=2)

    assert len(result) == 2
    assert result[0].metadata.relevance_score >= result[1].metadata.relevance_score


@pytest.mark.asyncio
async def test_rerank_empty_chunks():
    pipeline = _make_pipeline()
    assert await pipeline._rerank_chunks("test", [], top_k=5) == []


@pytest.mark.asyncio
async def test_generate_answer_no_chunks():
    pipeline = _make_pipeline()
    answer, input_tokens, output_tokens = await pipeline._generate_answer("test?", [])

    assert "couldn't find" in answer.lower()
    assert input_tokens == 0
    assert output_tokens == 0


def test_calculate_cost():
    pipeline = _make_pipeline()
    cost = pipeline._calculate_cost(embedding_tokens=1000, input_tokens=1000, output_tokens=100)

    # embed: 0.00002, input: 0.003, output: 0.0015 = $0.00452 = 0.452 cents
    assert cost == 0.452


def test_calculate_cost_zero():
    pipeline = _make_pipeline()
    assert pipeline._calculate_cost(0, 0, 0) == 0.0
