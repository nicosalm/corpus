"""PDF processing and semantic chunking service."""

import hashlib
import re
from datetime import datetime
from pathlib import Path

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.core.exceptions import ChunkingError, PDFProcessingError
from app.core.logging import get_logger
from app.models.domain import DocumentMetadata, TextChunk

logger = get_logger(__name__)


class PDFProcessor:
    """Handles PDF text extraction and semantic chunking."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def extract_text_from_pdf(self, pdf_path: str) -> tuple[str, DocumentMetadata]:
        """
        Extract text from PDF and metadata.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of (full_text, metadata)

        Raises:
            PDFProcessingError: If PDF cannot be processed
        """
        try:
            path = Path(pdf_path)
            if not path.exists():
                raise PDFProcessingError(f"PDF file not found: {pdf_path}")

            logger.info("extracting_pdf", file=pdf_path)

            doc = fitz.open(pdf_path)
            full_text = ""
            page_texts = []

            for page_num, page in enumerate(doc, start=1):
                text = page.get_text()
                page_texts.append((page_num, text))
                full_text += f"\n--- Page {page_num} ---\n{text}"

            doc.close()

            # Extract metadata from filename (e.g., "CS331_Lecture12.pdf")
            metadata = self._extract_metadata(pdf_path, len(page_texts))

            logger.info(
                "pdf_extracted",
                file=pdf_path,
                pages=len(page_texts),
                chars=len(full_text),
            )

            return full_text, metadata

        except Exception as e:
            raise PDFProcessingError(f"Failed to process PDF: {str(e)}") from e

    def chunk_text(
        self,
        text: str,
        metadata: DocumentMetadata,
    ) -> list[TextChunk]:
        """
        Split text into semantic chunks with metadata.

        Args:
            text: Full document text
            metadata: Document metadata

        Returns:
            List of TextChunk objects

        Raises:
            ChunkingError: If chunking fails
        """
        try:
            logger.info("chunking_text", file=metadata.file_name)

            # Split text using semantic boundaries
            chunk_texts = self.text_splitter.split_text(text)

            chunks: list[TextChunk] = []
            current_idx = 0

            for i, chunk_text in enumerate(chunk_texts):
                # Find chunk position in original text
                start_idx = text.find(chunk_text, current_idx)
                end_idx = start_idx + len(chunk_text)

                # Extract page number from chunk (look for "--- Page N ---")
                page_match = re.search(r"--- Page (\d+) ---", chunk_text)
                page_num = int(page_match.group(1)) if page_match else None

                # Generate unique chunk ID
                chunk_id = self._generate_chunk_id(metadata.file_name, i)

                chunk = TextChunk(
                    text=chunk_text.strip(),
                    chunk_id=chunk_id,
                    source_file=metadata.file_name,
                    page_num=page_num,
                    start_idx=start_idx,
                    end_idx=end_idx,
                    metadata={
                        "course": metadata.course or "",
                        "lecture": metadata.lecture or "",
                        "total_pages": metadata.total_pages,
                    },
                )

                chunks.append(chunk)
                current_idx = end_idx

            logger.info(
                "chunking_complete",
                file=metadata.file_name,
                num_chunks=len(chunks),
            )

            return chunks

        except Exception as e:
            raise ChunkingError(f"Failed to chunk text: {str(e)}") from e

    def process_pdf(self, pdf_path: str) -> tuple[list[TextChunk], DocumentMetadata]:
        """
        Full pipeline: extract PDF and create chunks.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of (chunks, metadata)
        """
        text, metadata = self.extract_text_from_pdf(pdf_path)
        chunks = self.chunk_text(text, metadata)
        return chunks, metadata

    def _extract_metadata(self, pdf_path: str, total_pages: int) -> DocumentMetadata:
        """
        Extract metadata from PDF filename and path.

        Expected patterns:
        - "CS331_Lecture12.pdf" -> course="CS331", lecture="Lecture12"
        - "path/to/CS150/notes.pdf" -> course="CS150"
        """
        path = Path(pdf_path)
        file_name = path.stem

        # Try to extract course and lecture from filename
        course_match = re.search(r"([A-Z]+\d+)", file_name)
        lecture_match = re.search(r"(Lecture|Lec|L)[\s_]?(\d+)", file_name, re.IGNORECASE)

        course = course_match.group(1) if course_match else None
        lecture = f"Lecture {lecture_match.group(2)}" if lecture_match else None

        # If not in filename, check parent directory
        if not course:
            for parent in path.parents:
                parent_match = re.search(r"([A-Z]+\d+)", parent.name)
                if parent_match:
                    course = parent_match.group(1)
                    break

        return DocumentMetadata(
            file_path=str(path.absolute()),
            file_name=path.name,
            course=course,
            lecture=lecture,
            date=None,  # Could extract from PDF metadata or filename
            total_pages=total_pages,
            extracted_at=datetime.utcnow().isoformat(),
        )

    @staticmethod
    def _generate_chunk_id(file_name: str, chunk_index: int) -> str:
        """Generate unique chunk ID from filename and index."""
        base = f"{file_name}_{chunk_index}"
        return hashlib.md5(base.encode()).hexdigest()[:16]
