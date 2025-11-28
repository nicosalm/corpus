"""Domain models for internal use."""

from pydantic import BaseModel, Field


class TextChunk(BaseModel):
    """Internal representation of a text chunk."""

    text: str
    chunk_id: str
    source_file: str
    page_num: int | None = None
    start_idx: int
    end_idx: int
    metadata: dict[str, str | int | float] = Field(default_factory=dict)


class EmbeddedChunk(BaseModel):
    """Text chunk with embedding vector."""

    chunk: TextChunk
    embedding: list[float]
    embedding_model: str


class ExtractedConcept(BaseModel):
    """Concept extracted from text."""

    name: str
    concept_type: str  # "topic", "person", "theory", "technique", etc.
    context: str  # surrounding text
    confidence: float = Field(ge=0.0, le=1.0)


class DocumentMetadata(BaseModel):
    """Metadata extracted from a PDF document."""

    file_path: str
    file_name: str
    course: str | None = None
    lecture: str | None = None
    date: str | None = None
    total_pages: int
    extracted_at: str  # ISO timestamp
