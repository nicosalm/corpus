import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.domain import TextChunk
from app.services.concept_extractor import ConceptExtractor


def _make_chunk(text: str = "Test text", chunk_id: str = "chunk_1") -> TextChunk:
    return TextChunk(
        text=text, chunk_id=chunk_id, source_file="test.pdf",
        start_idx=0, end_idx=len(text),
    )


def _mock_claude_response(concepts: list[dict]) -> MagicMock:
    response = MagicMock()
    response.content = [MagicMock(text=f"```json\n{json.dumps(concepts)}\n```")]
    return response


def _make_extractor(mock_response):
    with patch.object(ConceptExtractor, "__init__", lambda self: None):
        extractor = ConceptExtractor()
        extractor.settings = MagicMock()
        extractor.settings.claude_model = "claude-sonnet-4-5-20250929"
        extractor.client = AsyncMock()
        extractor.client.messages.create.return_value = mock_response
        return extractor


@pytest.mark.asyncio
async def test_extract_concepts_success():
    concepts_data = [
        {"name": "Dynamic Programming", "concept_type": "technique",
         "context": "optimization", "confidence": 0.95},
        {"name": "Memoization", "concept_type": "technique",
         "context": "caching results", "confidence": 0.85},
    ]
    extractor = _make_extractor(_mock_claude_response(concepts_data))
    result = await extractor.extract_concepts(_make_chunk())

    assert len(result) == 2
    assert result[0].name == "Dynamic Programming"
    assert result[0].confidence == 0.95


@pytest.mark.asyncio
async def test_extract_concepts_filters_invalid_types():
    concepts_data = [
        {"name": "Valid", "concept_type": "algorithm", "context": "ok", "confidence": 0.9},
        {"name": "Invalid", "concept_type": "banana", "context": "bad", "confidence": 0.9},
    ]
    extractor = _make_extractor(_mock_claude_response(concepts_data))
    result = await extractor.extract_concepts(_make_chunk())

    assert len(result) == 1
    assert result[0].name == "Valid"


@pytest.mark.asyncio
async def test_extract_concepts_clamps_confidence():
    concepts_data = [
        {"name": "High", "concept_type": "term", "context": "ctx", "confidence": 5.0},
        {"name": "Neg", "concept_type": "term", "context": "ctx", "confidence": -1.0},
    ]
    extractor = _make_extractor(_mock_claude_response(concepts_data))
    result = await extractor.extract_concepts(_make_chunk())

    assert len(result) == 2
    assert result[0].confidence == 0.5
    assert result[1].confidence == 0.5


@pytest.mark.asyncio
async def test_extract_concepts_handles_malformed_json():
    response = MagicMock()
    response.content = [MagicMock(text="This is not JSON")]
    extractor = _make_extractor(response)
    result = await extractor.extract_concepts(_make_chunk())

    assert result == []


@pytest.mark.asyncio
async def test_extract_concepts_handles_api_error():
    with patch.object(ConceptExtractor, "__init__", lambda self: None):
        extractor = ConceptExtractor()
        extractor.settings = MagicMock()
        extractor.settings.claude_model = "claude-sonnet-4-5-20250929"
        extractor.client = AsyncMock()
        extractor.client.messages.create.side_effect = RuntimeError("API down")

        result = await extractor.extract_concepts(_make_chunk())

    assert result == []


@pytest.mark.asyncio
async def test_extract_batch_concurrent():
    chunks = [_make_chunk(f"text {i}", f"chunk_{i}") for i in range(3)]
    concepts_data = [
        {"name": "Concept", "concept_type": "term", "context": "ctx", "confidence": 0.9},
    ]
    extractor = _make_extractor(_mock_claude_response(concepts_data))

    result = await extractor.extract_batch(chunks, max_concurrency=2)

    assert len(result) == 3
    for i in range(3):
        assert f"chunk_{i}" in result
        assert len(result[f"chunk_{i}"]) == 1


@pytest.mark.asyncio
async def test_extract_concepts_no_code_fences():
    concepts_data = [
        {"name": "Graph Theory", "concept_type": "topic",
         "context": "study of graphs", "confidence": 0.9},
    ]
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps(concepts_data))]
    extractor = _make_extractor(response)

    result = await extractor.extract_concepts(_make_chunk())

    assert len(result) == 1
    assert result[0].name == "Graph Theory"
