import shutil
import tempfile
import time
from itertools import combinations
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile

from app.api.dependencies import (
    get_concept_extractor,
    get_embedding_service,
    get_neo4j_client,
)
from app.core.logging import get_logger
from app.models.schemas import IngestRequest, IngestResponse
from app.services.concept_extractor import ConceptExtractor
from app.services.embeddings import EmbeddingService
from app.services.neo4j_client import Neo4jClient
from app.services.pdf_processor import PDFProcessor

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


async def _process_single_pdf(
    file_path: str,
    processor: PDFProcessor,
    neo4j: Neo4jClient,
    embeddings: EmbeddingService,
    concept_extractor: ConceptExtractor,
) -> tuple[int, int]:
    """Returns (chunks_created, concepts_extracted)."""
    chunks, _metadata = processor.process_pdf(file_path)

    embedded_chunks, _tokens = await embeddings.embed_chunks(chunks)
    await neo4j.store_chunks(embedded_chunks)

    chunk_concepts = await concept_extractor.extract_batch(chunks)

    total_concepts = 0
    all_concept_pairs: list[tuple[str, str]] = []

    for chunk_id, concepts in chunk_concepts.items():
        if concepts:
            await neo4j.store_concepts(concepts, chunk_id)
            total_concepts += len(concepts)

            concept_names = [c.name for c in concepts]
            if len(concept_names) > 1:
                all_concept_pairs.extend(combinations(concept_names, 2))

    if all_concept_pairs:
        await neo4j.create_concept_relations(all_concept_pairs)

    return len(chunks), total_concepts


@router.post("", response_model=IngestResponse)
async def ingest_pdfs(
    request: IngestRequest,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
    embeddings: EmbeddingService = Depends(get_embedding_service),
    concept_extractor: ConceptExtractor = Depends(get_concept_extractor),
) -> IngestResponse:
    start_time = time.time()
    processor = PDFProcessor()

    files_processed = 0
    total_chunks = 0
    total_concepts = 0
    errors: list[str] = []

    logger.info("ingestion_started", num_files=len(request.file_paths))

    for file_path in request.file_paths:
        try:
            if not Path(file_path).exists():
                errors.append(f"File not found: {file_path}")
                continue

            chunks_created, concepts_extracted = await _process_single_pdf(
                file_path, processor, neo4j, embeddings, concept_extractor,
            )
            files_processed += 1
            total_chunks += chunks_created
            total_concepts += concepts_extracted

            logger.info("file_ingested", file=file_path, chunks=chunks_created)

        except Exception as e:
            errors.append(f"Failed to process {file_path}: {e}")
            logger.error("file_ingestion_failed", file=file_path, error=str(e))

    processing_time_ms = (time.time() - start_time) * 1000
    return IngestResponse(
        files_processed=files_processed,
        chunks_created=total_chunks,
        concepts_extracted=total_concepts,
        processing_time_ms=processing_time_ms,
        errors=errors,
    )


@router.post("/upload", response_model=IngestResponse)
async def upload_pdfs(
    files: list[UploadFile],
    neo4j: Neo4jClient = Depends(get_neo4j_client),
    embeddings: EmbeddingService = Depends(get_embedding_service),
    concept_extractor: ConceptExtractor = Depends(get_concept_extractor),
) -> IngestResponse:
    start_time = time.time()
    processor = PDFProcessor()

    files_processed = 0
    total_chunks = 0
    total_concepts = 0
    errors: list[str] = []
    tmp_dir = tempfile.mkdtemp(prefix="corpus_upload_")

    logger.info("upload_ingestion_started", num_files=len(files))

    try:
        for upload_file in files:
            filename = upload_file.filename or "upload.pdf"

            if not filename.lower().endswith(".pdf"):
                errors.append(f"Not a PDF: {filename}")
                continue

            tmp_path = Path(tmp_dir) / filename

            try:
                with open(tmp_path, "wb") as f:
                    shutil.copyfileobj(upload_file.file, f)

                chunks_created, concepts_extracted = await _process_single_pdf(
                    str(tmp_path), processor, neo4j, embeddings, concept_extractor,
                )
                files_processed += 1
                total_chunks += chunks_created
                total_concepts += concepts_extracted

                logger.info("uploaded_file_ingested", file=filename, chunks=chunks_created)

            except Exception as e:
                errors.append(f"Failed to process {filename}: {e}")
                logger.error("uploaded_file_ingestion_failed", file=filename, error=str(e))

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    processing_time_ms = (time.time() - start_time) * 1000
    return IngestResponse(
        files_processed=files_processed,
        chunks_created=total_chunks,
        concepts_extracted=total_concepts,
        processing_time_ms=processing_time_ms,
        errors=errors,
    )
