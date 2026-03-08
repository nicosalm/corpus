from pydantic import BaseModel, Field


class TextChunk(BaseModel):
    text: str
    chunk_id: str
    source_file: str
    page_num: int | None = None
    start_idx: int
    end_idx: int
    metadata: dict[str, str | int | float] = Field(default_factory=dict)


class EmbeddedChunk(BaseModel):
    chunk: TextChunk
    embedding: list[float]
    embedding_model: str


class ExtractedConcept(BaseModel):
    name: str
    concept_type: str
    context: str
    confidence: float = Field(ge=0.0, le=1.0)


class DocumentMetadata(BaseModel):
    file_path: str
    file_name: str
    course: str | None = None
    lecture: str | None = None
    date: str | None = None
    total_pages: int
    extracted_at: str
