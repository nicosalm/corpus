#!/usr/bin/env python3
"""Script to ingest PDF files from data/raw directory."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.services.embeddings import EmbeddingService
from app.services.neo4j_client import Neo4jClient
from app.services.pdf_processor import PDFProcessor


setup_logging()
logger = get_logger(__name__)


async def ingest_directory(directory: Path) -> None:
    """
    Ingest all PDFs from a directory.

    Args:
        directory: Path to directory containing PDFs
    """
    settings = get_settings()
    logger.info("ingestion_started", directory=str(directory))

    # Initialize services
    pdf_processor = PDFProcessor()
    embedding_service = EmbeddingService()
    neo4j_client = Neo4jClient()

    try:
        # Connect to services
        await embedding_service.connect_redis()
        await neo4j_client.connect()

        # Find all PDF files
        pdf_files = list(directory.glob("**/*.pdf"))
        logger.info("pdfs_found", count=len(pdf_files))

        if not pdf_files:
            logger.warning("no_pdfs_found", directory=str(directory))
            return

        total_chunks = 0
        processed_files = 0

        for pdf_path in pdf_files:
            try:
                logger.info("processing_file", file=str(pdf_path))

                # Process PDF
                chunks, metadata = pdf_processor.process_pdf(str(pdf_path))
                logger.info("pdf_processed", file=pdf_path.name, chunks=len(chunks))

                # Generate embeddings
                embedded_chunks = await embedding_service.embed_chunks(chunks)
                logger.info("embeddings_generated", count=len(embedded_chunks))

                # Store in Neo4j
                await neo4j_client.store_chunks(embedded_chunks)
                logger.info("chunks_stored", count=len(embedded_chunks))

                total_chunks += len(chunks)
                processed_files += 1

            except Exception as e:
                logger.error("file_processing_failed", file=str(pdf_path), error=str(e))
                continue

        logger.info(
            "ingestion_complete",
            processed_files=processed_files,
            total_files=len(pdf_files),
            total_chunks=total_chunks,
        )

    finally:
        # Cleanup
        await embedding_service.close_redis()
        await neo4j_client.close()


def main() -> None:
    """Main entry point."""
    # Get data directory
    data_dir = Path(__file__).parent.parent / "data" / "raw"

    if not data_dir.exists():
        logger.error("data_directory_not_found", path=str(data_dir))
        sys.exit(1)

    # Run ingestion
    asyncio.run(ingest_directory(data_dir))


if __name__ == "__main__":
    main()
