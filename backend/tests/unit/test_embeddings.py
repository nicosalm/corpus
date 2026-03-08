import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.domain import EmbeddedChunk, TextChunk
from app.services.embeddings import EmbeddingService


def _make_chunk(text: str = "test text", chunk_id: str = "c1") -> TextChunk:
    return TextChunk(
        text=text, chunk_id=chunk_id, source_file="test.pdf",
        start_idx=0, end_idx=len(text),
    )


def _make_service(*, redis_client=None, embed_response=None):
    with patch.object(EmbeddingService, "__init__", lambda self: None):
        service = EmbeddingService()
        service.settings = MagicMock()
        service.settings.embedding_model = "text-embedding-3-small"
        service.redis_client = redis_client
        service.client = AsyncMock()

        if embed_response:
            service.client.embeddings.create.return_value = embed_response

        return service


def _mock_openai_response(embedding=None, tokens=5):
    response = MagicMock()
    response.data = [MagicMock(embedding=embedding or [0.1] * 1536)]
    response.usage.total_tokens = tokens
    return response


@pytest.mark.asyncio
async def test_embed_text_cache_miss():
    service = _make_service(embed_response=_mock_openai_response(tokens=5))

    embedding, tokens = await service.embed_text("hello")

    assert len(embedding) == 1536
    assert tokens == 5
    service.client.embeddings.create.assert_called_once()


@pytest.mark.asyncio
async def test_embed_text_cache_hit():
    cached = [0.2] * 1536
    redis_client = AsyncMock()
    redis_client.get.return_value = json.dumps(cached).encode()

    service = _make_service(redis_client=redis_client)

    embedding, tokens = await service.embed_text("hello")

    assert embedding == cached
    assert tokens == 0
    service.client.embeddings.create.assert_not_called()


@pytest.mark.asyncio
async def test_embed_text_cache_write_failure_continues():
    redis_client = AsyncMock()
    redis_client.get.return_value = None
    redis_client.setex.side_effect = ConnectionError("Redis down")

    service = _make_service(redis_client=redis_client, embed_response=_mock_openai_response())

    embedding, tokens = await service.embed_text("hello")

    assert len(embedding) == 1536
    assert tokens == 5


@pytest.mark.asyncio
async def test_embed_chunks_aggregates_tokens():
    service = _make_service()
    service.embed_text = AsyncMock(return_value=([0.1] * 1536, 10))

    chunks = [_make_chunk(f"text {i}", f"chunk_{i}") for i in range(3)]
    embedded, total_tokens = await service.embed_chunks(chunks)

    assert len(embedded) == 3
    assert total_tokens == 30
    assert all(isinstance(ec, EmbeddedChunk) for ec in embedded)


@pytest.mark.asyncio
async def test_embed_query_delegates_to_embed_text():
    service = _make_service()
    service.embed_text = AsyncMock(return_value=([0.5] * 1536, 8))

    embedding, tokens = await service.embed_query("what is DP?")

    assert tokens == 8
    service.embed_text.assert_called_once_with("what is DP?")


def test_cache_key_deterministic():
    service = _make_service()

    key1 = service._get_cache_key("hello world")
    key2 = service._get_cache_key("hello world")
    key3 = service._get_cache_key("different text")

    assert key1 == key2
    assert key1 != key3
    assert key1.startswith("emb:")
