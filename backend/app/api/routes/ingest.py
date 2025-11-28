"""PDF ingestion endpoint."""

import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.core.logging import get_logger
from app.models.schemas import IngestRequest, IngestResponse
from app.services.embeddings import EmbeddingService
from app.services.neo4j_client import Neo4jClient
from app.services.pdf_processor import PDFProcessor
from app.api.dependencies import get_embedding_service, get_neo4j_client

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
async def ingest_pdfs(
    request: IngestRequest,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
    embeddings: EmbeddingService = Depends(get_embedding_service),
) -> IngestResponse:
    """
    Ingest PDF documents into the knowledge base.

    Args:
        request: Ingestion request with file paths
        neo4j: Neo4j client (injected)
        embeddings: Embedding service (injected)

    Returns:
        Ingestion results and statistics
    """
    start_time = time.time()
    processor = PDFProcessor()

    files_processed = 0
    total_chunks = 0
    errors: list[str] = []

    try:
        logger.info("ingestion_started", num_files=len(request.file_paths))

        for file_path in request.file_paths:
            try:
                # Validate file exists
                if not Path(file_path).exists():
                    errors.append(f"File not found: {file_path}")
                    continue

                # Process PDF
                chunks, metadata = processor.process_pdf(file_path)

                # Generate embeddings
                embedded_chunks = await embeddings.embed_chunks(chunks)

                # Store in Neo4j
                await neo4j.store_chunks(embedded_chunks)

                files_processed += 1
                total_chunks += len(chunks)

                logger.info(
                    "file_ingested",
                    file=file_path,
                    chunks=len(chunks),
                )

            except Exception as e:
                error_msg = f"Failed to process {file_path}: {str(e)}"
                errors.append(error_msg)
                logger.error("file_ingestion_failed", file=file_path, error=str(e))

        processing_time_ms = (time.time() - start_time) * 1000

        logger.info(
            "ingestion_complete",
            files_processed=files_processed,
            total_chunks=total_chunks,
            errors=len(errors),
        )

        return IngestResponse(
            files_processed=files_processed,
            chunks_created=total_chunks,
            concepts_extracted=0,  # TODO: implement concept extraction
            processing_time_ms=processing_time_ms,
            errors=errors,
        )

    except Exception as e:
        logger.error("ingestion_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
