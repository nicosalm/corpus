"""Pydantic models for API requests and responses."""

from datetime import datetime

from pydantic import BaseModel, Field


# API Request/Response Models
class QueryRequest(BaseModel):
    """Request model for RAG query endpoint."""

    question: str = Field(..., min_length=1, description="User question")
    max_chunks: int = Field(default=5, ge=1, le=20, description="Maximum chunks to return")
    include_graph: bool = Field(default=True, description="Include concept graph in response")


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""

    chunk_id: str
    course: str | None = None
    lecture: str | None = None
    topic: str | None = None
    page_num: int | None = None
    relevance_score: float | None = None


class DocumentChunk(BaseModel):
    """Retrieved document chunk with metadata."""

    content: str
    metadata: ChunkMetadata


class ConceptNode(BaseModel):
    """Graph concept node."""

    name: str
    node_type: str  # "concept", "course", "document"
    description: str | None = None


class ConceptEdge(BaseModel):
    """Graph edge between concepts."""

    source: str
    target: str
    edge_type: str  # "RELATES_TO", "PREREQUISITE", "MENTIONED_IN", "CONTAINS"
    weight: float | None = None


class ConceptGraph(BaseModel):
    """Knowledge graph structure."""

    nodes: list[ConceptNode]
    edges: list[ConceptEdge]


class QueryResponse(BaseModel):
    """Response model for RAG query endpoint."""

    answer: str
    chunks: list[DocumentChunk]
    graph: ConceptGraph | None = None
    processing_time_ms: float
    cost_estimate_cents: float | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    neo4j_connected: bool
    redis_connected: bool
    timestamp: datetime


class IngestRequest(BaseModel):
    """Request to ingest PDF documents."""

    file_paths: list[str] = Field(..., min_length=1, description="Paths to PDF files")
    course_name: str | None = Field(None, description="Course name override")
    overwrite: bool = Field(default=False, description="Overwrite existing chunks")


class IngestResponse(BaseModel):
    """Response from PDF ingestion."""

    files_processed: int
    chunks_created: int
    concepts_extracted: int
    processing_time_ms: float
    errors: list[str] = Field(default_factory=list)
