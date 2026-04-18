import pytest
from pydantic import ValidationError

from app.models.schemas import (
    ChunkMetadata,
    Citation,
    DocumentChunk,
    QueryResponse,
)


def test_citation_rejects_empty_quote():
    """Empty quote would bypass the quote-span hallucination guard, so schema rejects it."""
    with pytest.raises(ValidationError):
        Citation(chunk_id="chunk_0", quote="")


def test_citation_accepts_single_char_quote():
    citation = Citation(chunk_id="chunk_0", quote="x")
    assert citation.quote == "x"


def test_query_response_round_trips_citations_through_json():
    """Cache layer serializes via model_dump_json and reloads via model_validate_json.
    Citations must survive that round-trip with fields intact.
    """
    original = QueryResponse(
        answer="DP reuses subproblem solutions.",
        citations=[
            Citation(chunk_id="chunk_0", quote="overlapping subproblems"),
            Citation(chunk_id="chunk_1", quote="optimal substructure"),
        ],
        chunks=[
            DocumentChunk(
                content="overlapping subproblems and optimal substructure",
                metadata=ChunkMetadata(chunk_id="chunk_0", course="CS577"),
            ),
        ],
        processing_time_ms=123.4,
        cost_cents=0.42,
    )

    payload = original.model_dump_json()
    restored = QueryResponse.model_validate_json(payload)

    assert restored.answer == original.answer
    assert len(restored.citations) == 2
    assert restored.citations[0].chunk_id == "chunk_0"
    assert restored.citations[0].quote == "overlapping subproblems"
    assert restored.citations[1].chunk_id == "chunk_1"
    assert restored.cost_cents == 0.42
    assert restored.cached is False


def test_query_response_defaults_citations_to_empty_list():
    response = QueryResponse(
        answer="a",
        chunks=[],
        processing_time_ms=1.0,
        cost_cents=0.0,
    )
    assert response.citations == []
