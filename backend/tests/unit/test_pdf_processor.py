from app.services.pdf_processor import PDFProcessor


def test_generate_chunk_id():
    id1 = PDFProcessor._generate_chunk_id("test.pdf", 0)
    id2 = PDFProcessor._generate_chunk_id("test.pdf", 1)

    assert id1 != id2
    assert len(id1) == 16


def test_extract_metadata_from_filename():
    processor = PDFProcessor()
    metadata = processor._extract_metadata("/path/to/CS331_Lecture12.pdf", total_pages=10)

    assert metadata.course == "CS331"
    assert metadata.lecture == "Lecture 12"
    assert metadata.total_pages == 10
    assert metadata.file_name == "CS331_Lecture12.pdf"


def test_extract_metadata_no_course():
    processor = PDFProcessor()
    metadata = processor._extract_metadata("/path/to/random_notes.pdf", total_pages=5)

    assert metadata.course is None
    assert metadata.lecture is None
    assert metadata.total_pages == 5
