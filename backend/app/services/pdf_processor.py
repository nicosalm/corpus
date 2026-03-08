import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

import fitz
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.core.exceptions import ChunkingError, PDFProcessingError
from app.core.logging import get_logger
from app.models.domain import DocumentMetadata, TextChunk

logger = get_logger(__name__)


class PDFProcessor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def extract_text_from_pdf(self, pdf_path: str) -> tuple[str, DocumentMetadata]:
        try:
            path = Path(pdf_path)
            if not path.exists():
                raise PDFProcessingError(f"PDF file not found: {pdf_path}")

            logger.info("extracting_pdf", file=pdf_path)

            doc = fitz.open(pdf_path)
            full_text = ""
            page_count = 0

            for page_num, page in enumerate(doc, start=1):
                full_text += f"\n--- Page {page_num} ---\n{page.get_text()}"
                page_count += 1

            doc.close()

            metadata = self._extract_metadata(pdf_path, page_count)
            logger.info("pdf_extracted", file=pdf_path, pages=page_count, chars=len(full_text))
            return full_text, metadata

        except PDFProcessingError:
            raise
        except Exception as e:
            raise PDFProcessingError(f"Failed to process PDF: {e}") from e

    def chunk_text(self, text: str, metadata: DocumentMetadata) -> list[TextChunk]:
        try:
            logger.info("chunking_text", file=metadata.file_name)
            chunk_texts = self.text_splitter.split_text(text)

            chunks: list[TextChunk] = []
            current_idx = 0

            for i, chunk_text in enumerate(chunk_texts):
                start_idx = text.find(chunk_text, current_idx)
                end_idx = start_idx + len(chunk_text)

                page_match = re.search(r"--- Page (\d+) ---", chunk_text)
                page_num = int(page_match.group(1)) if page_match else None

                chunks.append(TextChunk(
                    text=chunk_text.strip(),
                    chunk_id=self._generate_chunk_id(metadata.file_name, i),
                    source_file=metadata.file_name,
                    page_num=page_num,
                    start_idx=start_idx,
                    end_idx=end_idx,
                    metadata={
                        "course": metadata.course or "",
                        "lecture": metadata.lecture or "",
                        "total_pages": metadata.total_pages,
                    },
                ))
                current_idx = end_idx

            logger.info("chunking_complete", file=metadata.file_name, num_chunks=len(chunks))
            return chunks

        except Exception as e:
            raise ChunkingError(f"Failed to chunk text: {e}") from e

    def process_pdf(self, pdf_path: str) -> tuple[list[TextChunk], DocumentMetadata]:
        text, metadata = self.extract_text_from_pdf(pdf_path)
        chunks = self.chunk_text(text, metadata)
        return chunks, metadata

    def _extract_metadata(self, pdf_path: str, total_pages: int) -> DocumentMetadata:
        path = Path(pdf_path)
        file_name = path.stem

        course_match = re.search(r"([A-Z]+\d+)", file_name)
        lecture_match = re.search(r"(Lecture|Lec|L)[\s_]?(\d+)", file_name, re.IGNORECASE)

        course = course_match.group(1) if course_match else None
        lecture = f"Lecture {lecture_match.group(2)}" if lecture_match else None

        # Fall back to parent directory for course name
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
            date=None,
            total_pages=total_pages,
            extracted_at=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def _generate_chunk_id(file_name: str, chunk_index: int) -> str:
        base = f"{file_name}_{chunk_index}"
        return hashlib.md5(base.encode()).hexdigest()[:16]
