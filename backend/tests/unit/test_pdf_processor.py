"""Unit tests for PDF processor."""

import pytest

from app.services.pdf_processor import PDFProcessor


def test_generate_chunk_id():
    """Test chunk ID generation."""
    chunk_id_1 = PDFProcessor._generate_chunk_id("test.pdf", 0)
    chunk_id_2 = PDFProcessor._generate_chunk_id("test.pdf", 1)

    assert chunk_id_1 != chunk_id_2
    assert len(chunk_id_1) == 16  # MD5 hash truncated to 16 chars


def test_extract_metadata_from_filename():
    """Test metadata extraction from filename."""
    processor = PDFProcessor()

    metadata = processor._extract_metadata("/path/to/CS331_Lecture12.pdf", total_pages=10)

    assert metadata.course == "CS331"
    assert metadata.lecture == "Lecture 12"
    assert metadata.total_pages == 10
    assert metadata.file_name == "CS331_Lecture12.pdf"


def test_extract_metadata_no_course():
    """Test metadata extraction when course is not in filename."""
    processor = PDFProcessor()

    metadata = processor._extract_metadata("/path/to/random_notes.pdf", total_pages=5)

    assert metadata.course is None
    assert metadata.lecture is None
    assert metadata.total_pages == 5
