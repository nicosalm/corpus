"""PDF ingestion endpoint."""

import time
from itertools import combinations
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.core.logging import get_logger
from app.models.schemas import IngestRequest, IngestResponse
from app.services.concept_extractor import ConceptExtractor
from app.services.embeddings import EmbeddingService
from app.services.neo4j_client import Neo4jClient
from app.services.pdf_processor import PDFProcessor
from app.api.dependencies import (
    get_concept_extractor,
    get_embedding_service,
    get_neo4j_client,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
async def ingest_pdfs(
    request: IngestRequest,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
    embeddings: EmbeddingService = Depends(get_embedding_service),
    concept_extractor: ConceptExtractor = Depends(get_concept_extractor),
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
    total_concepts = 0
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
                embedded_chunks, _tokens = await embeddings.embed_chunks(chunks)

                # Store in Neo4j
                await neo4j.store_chunks(embedded_chunks)

                # Extract concepts from each chunk
                all_chunk_concept_pairs: list[tuple[str, str]] = []

                for chunk in chunks:
                    concepts = await concept_extractor.extract_concepts(chunk)

                    if concepts:
                        # Store concepts and link to chunk
                        await neo4j.store_concepts(concepts, chunk.chunk_id)
                        total_concepts += len(concepts)

                        # Build relationships WITHIN this chunk only
                        chunk_concept_names = [c.name for c in concepts]
                        if len(chunk_concept_names) > 1:
                            # Concepts in same chunk are strongly related
                            chunk_pairs = list(combinations(chunk_concept_names, 2))
                            all_chunk_concept_pairs.extend(chunk_pairs)

                # Create all concept relationships in batch
                if all_chunk_concept_pairs:
                    await neo4j.create_concept_relations(all_chunk_concept_pairs)
                    logger.info(
                        "concept_relations_created",
                        file=file_path,
                        num_pairs=len(all_chunk_concept_pairs),
                        unique_pairs=len(set(all_chunk_concept_pairs)),
                    )

                files_processed += 1
                total_chunks += len(chunks)

                logger.info(
                    "file_ingested",
                    file=file_path,
                    chunks=len(chunks),
                    concept_pairs=len(all_chunk_concept_pairs),
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
            total_concepts=total_concepts,
            errors=len(errors),
        )

        return IngestResponse(
            files_processed=files_processed,
            chunks_created=total_chunks,
            concepts_extracted=total_concepts,
            processing_time_ms=processing_time_ms,
            errors=errors,
        )

    except Exception as e:
        logger.error("ingestion_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
