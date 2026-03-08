import io
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.domain import DocumentMetadata, EmbeddedChunk, TextChunk


def _mock_services():
    mock_neo4j = AsyncMock()
    mock_embeddings = AsyncMock()
    mock_concept_extractor = AsyncMock()
    mock_embeddings.embed_chunks.return_value = ([], 0)
    mock_concept_extractor.extract_batch.return_value = {}
    return mock_neo4j, mock_embeddings, mock_concept_extractor


@pytest.mark.asyncio
async def test_upload_pdf_success():
    mock_neo4j, mock_embeddings, mock_concept_extractor = _mock_services()

    mock_chunk = TextChunk(
        text="Test content", chunk_id="test_chunk",
        source_file="test.pdf", start_idx=0, end_idx=12,
    )
    mock_metadata = DocumentMetadata(
        file_path="/tmp/test.pdf", file_name="test.pdf",
        total_pages=1, extracted_at="2025-01-01T00:00:00",
    )
    mock_embedded = EmbeddedChunk(
        chunk=mock_chunk, embedding=[0.1] * 1536,
        embedding_model="text-embedding-3-small",
    )
    mock_embeddings.embed_chunks.return_value = ([mock_embedded], 10)

    with patch("app.api.dependencies._neo4j_client", mock_neo4j), \
         patch("app.api.dependencies._embedding_service", mock_embeddings), \
         patch("app.api.dependencies._concept_extractor", mock_concept_extractor), \
         patch("app.api.routes.ingest.PDFProcessor") as mock_proc:

        mock_proc.return_value.process_pdf.return_value = ([mock_chunk], mock_metadata)

        files = [("files", ("test.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf"))]
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/ingest/upload", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["files_processed"] == 1
    assert data["chunks_created"] == 1


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf():
    mock_neo4j, mock_embeddings, mock_concept_extractor = _mock_services()

    with patch("app.api.dependencies._neo4j_client", mock_neo4j), \
         patch("app.api.dependencies._embedding_service", mock_embeddings), \
         patch("app.api.dependencies._concept_extractor", mock_concept_extractor):

        files = [("files", ("notes.txt", io.BytesIO(b"not a pdf"), "text/plain"))]
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/ingest/upload", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["files_processed"] == 0
    assert "Not a PDF" in data["errors"][0]


@pytest.mark.asyncio
async def test_ingest_by_path_file_not_found():
    mock_neo4j, mock_embeddings, mock_concept_extractor = _mock_services()

    with patch("app.api.dependencies._neo4j_client", mock_neo4j), \
         patch("app.api.dependencies._embedding_service", mock_embeddings), \
         patch("app.api.dependencies._concept_extractor", mock_concept_extractor):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/ingest", json={"file_paths": ["/nonexistent/file.pdf"]})

    assert response.status_code == 200
    data = response.json()
    assert data["files_processed"] == 0
    assert "not found" in data["errors"][0].lower()
