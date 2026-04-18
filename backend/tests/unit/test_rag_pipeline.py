from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import RAGPipelineError
from app.models.schemas import ChunkMetadata, Citation, DocumentChunk
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
    citations = [Citation(chunk_id="chunk_0", quote="content about algorithms")]
    pipeline = _make_pipeline(
        embedding_service=AsyncMock(**{"embed_query.return_value": ([0.1] * 1536, 10)}),
        neo4j_client=AsyncMock(**{"vector_search.return_value": chunks}),
    )
    pipeline._rerank_chunks = AsyncMock(return_value=chunks[:2])
    pipeline._generate_answer = AsyncMock(
        return_value=("The answer is 42.", citations, 500, 100),
    )
    pipeline._build_concept_graph = AsyncMock(return_value=None)
    pipeline._calculate_cost = MagicMock(return_value=0.05)

    result = await pipeline.query("What is DP?", max_chunks=2, include_graph=True)

    assert result.answer == "The answer is 42."
    assert len(result.chunks) == 2
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "chunk_0"
    assert result.cost_cents == 0.05
    assert result.processing_time_ms > 0


@pytest.mark.asyncio
async def test_query_drops_hallucinated_citations():
    """If Claude cites a chunk_id that was never retrieved, the pipeline drops it."""
    chunks = _make_chunks(2)
    raw_citations = [
        Citation(chunk_id="chunk_0", quote="Chunk 0 content"),
        Citation(chunk_id="chunk_99", quote="hallucinated span"),
    ]
    pipeline = _make_pipeline(
        embedding_service=AsyncMock(**{"embed_query.return_value": ([0.1] * 1536, 10)}),
        neo4j_client=AsyncMock(**{"vector_search.return_value": chunks}),
    )
    pipeline._rerank_chunks = AsyncMock(return_value=chunks)
    pipeline._generate_answer = AsyncMock(
        return_value=("answer", raw_citations, 100, 50),
    )
    pipeline._build_concept_graph = AsyncMock(return_value=None)
    pipeline._calculate_cost = MagicMock(return_value=0.01)

    result = await pipeline.query("q", max_chunks=2, include_graph=False)

    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "chunk_0"


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
    answer, citations, input_tokens, output_tokens = await pipeline._generate_answer("test?", [])

    assert "couldn't find" in answer.lower()
    assert citations == []
    assert input_tokens == 0
    assert output_tokens == 0


@pytest.mark.asyncio
async def test_generate_answer_uses_tool_response():
    """Happy path: Claude returns a tool_use block and the pipeline parses it."""
    pipeline = _make_pipeline()
    pipeline.settings.claude_model = "claude-test"
    tool_use_block = SimpleNamespace(
        type="tool_use",
        name="answer_with_citations",
        input={
            "answer": "Dynamic programming solves overlapping subproblems.",
            "citations": [
                {"chunk_id": "chunk_0", "quote": "overlapping subproblems"},
                {"chunk_id": "chunk_1", "quote": "DP is about reuse"},
            ],
        },
    )
    mock_response = SimpleNamespace(
        content=[tool_use_block],
        usage=SimpleNamespace(input_tokens=300, output_tokens=80),
    )
    pipeline.claude_client = AsyncMock()
    pipeline.claude_client.messages.create.return_value = mock_response

    answer, citations, input_tokens, output_tokens = await pipeline._generate_answer(
        "What is DP?", _make_chunks(2),
    )

    assert "Dynamic programming" in answer
    assert len(citations) == 2
    assert citations[0].chunk_id == "chunk_0"
    assert citations[1].quote == "DP is about reuse"
    assert input_tokens == 300
    assert output_tokens == 80


@pytest.mark.asyncio
async def test_generate_answer_raises_when_no_tool_use():
    """If Claude returns only text with no tool_use block, we surface a RAGPipelineError."""
    pipeline = _make_pipeline()
    pipeline.settings.claude_model = "claude-test"
    text_block = SimpleNamespace(type="text", text="just prose, no tool call")
    mock_response = SimpleNamespace(
        content=[text_block],
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )
    pipeline.claude_client = AsyncMock()
    pipeline.claude_client.messages.create.return_value = mock_response

    with pytest.raises(RAGPipelineError, match="did not call answer_with_citations"):
        await pipeline._generate_answer("q", _make_chunks(1))


def test_validate_citations_keeps_retrieved_ids_with_matching_quotes():
    chunks = _make_chunks(3)
    citations = [
        Citation(chunk_id="chunk_0", quote="content about algorithms"),
        Citation(chunk_id="chunk_2", quote="Chunk 2 content"),
    ]
    kept = RAGPipeline._validate_citations(citations, chunks)

    assert [c.chunk_id for c in kept] == ["chunk_0", "chunk_2"]


def test_validate_citations_drops_hallucinated_ids():
    chunks = _make_chunks(2)
    citations = [
        Citation(chunk_id="chunk_0", quote="Chunk 0 content"),
        Citation(chunk_id="chunk_fake", quote="fabricated"),
        Citation(chunk_id="chunk_1", quote="Chunk 1 content"),
    ]
    kept = RAGPipeline._validate_citations(citations, chunks)

    assert len(kept) == 2
    assert "chunk_fake" not in [c.chunk_id for c in kept]


def test_validate_citations_drops_quote_not_in_chunk():
    """Real chunk_id but fabricated quote - caught by quote-span check."""
    chunks = _make_chunks(1)  # content: "Chunk 0 content about algorithms"
    citations = [
        Citation(chunk_id="chunk_0", quote="entirely fabricated sentence not in the source"),
    ]
    kept = RAGPipeline._validate_citations(citations, chunks)

    assert kept == []


def test_validate_citations_normalizes_whitespace_and_case():
    """LLMs sometimes tweak whitespace or capitalization - we forgive that."""
    chunks = _make_chunks(1)  # content: "Chunk 0 content about algorithms"
    citations = [
        Citation(chunk_id="chunk_0", quote="CONTENT   about\nalgorithms"),
    ]
    kept = RAGPipeline._validate_citations(citations, chunks)

    assert len(kept) == 1


def test_validate_citations_handles_empty_inputs():
    assert RAGPipeline._validate_citations([], _make_chunks(2)) == []
    citations = [Citation(chunk_id="chunk_0", quote="x")]
    assert RAGPipeline._validate_citations(citations, []) == []


def test_quote_in_chunk_normalizes():
    """Unit test the normalization helper directly."""
    assert RAGPipeline._quote_in_chunk("hello", "HELLO world") is True
    assert RAGPipeline._quote_in_chunk("hello  world", "hello world") is True
    assert RAGPipeline._quote_in_chunk("not present", "hello world") is False
    assert RAGPipeline._quote_in_chunk("  padded  ", "padded") is True


def test_parse_tool_response_extracts_payload():
    tool_use = SimpleNamespace(
        type="tool_use",
        name="answer_with_citations",
        input={
            "answer": "the answer",
            "citations": [{"chunk_id": "chunk_0", "quote": "q"}],
        },
    )
    response = SimpleNamespace(content=[tool_use])

    answer, citations = RAGPipeline._parse_tool_response(response)

    assert answer == "the answer"
    assert len(citations) == 1
    assert citations[0].chunk_id == "chunk_0"


def test_parse_tool_response_skips_malformed_citations():
    """Malformed citation items are logged and dropped; valid ones survive."""
    tool_use = SimpleNamespace(
        type="tool_use",
        name="answer_with_citations",
        input={
            "answer": "ok",
            "citations": [
                {"chunk_id": "chunk_0", "quote": "valid"},
                {"chunk_id": "chunk_1"},  # missing quote
                "not an object",
            ],
        },
    )
    response = SimpleNamespace(content=[tool_use])

    answer, citations = RAGPipeline._parse_tool_response(response)

    assert answer == "ok"
    assert len(citations) == 1
    assert citations[0].chunk_id == "chunk_0"


def test_parse_tool_response_raises_without_tool_block():
    text_only = SimpleNamespace(type="text", text="nope")
    response = SimpleNamespace(content=[text_only])

    with pytest.raises(RAGPipelineError):
        RAGPipeline._parse_tool_response(response)


def test_calculate_cost():
    pipeline = _make_pipeline()
    cost = pipeline._calculate_cost(embedding_tokens=1000, input_tokens=1000, output_tokens=100)

    # embed: 0.00002, input: 0.003, output: 0.0015 = $0.00452 = 0.452 cents
    assert cost == 0.452


def test_calculate_cost_zero():
    pipeline = _make_pipeline()
    assert pipeline._calculate_cost(0, 0, 0) == 0.0
