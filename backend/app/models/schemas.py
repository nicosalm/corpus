from datetime import datetime

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    max_chunks: int = Field(default=5, ge=1, le=20)
    include_graph: bool = True


class ChunkMetadata(BaseModel):
    chunk_id: str
    course: str | None = None
    lecture: str | None = None
    topic: str | None = None
    page_num: int | None = None
    relevance_score: float | None = None


class DocumentChunk(BaseModel):
    content: str
    metadata: ChunkMetadata


class ConceptNode(BaseModel):
    name: str
    node_type: str
    description: str | None = None


class ConceptEdge(BaseModel):
    source: str
    target: str
    edge_type: str
    weight: float | None = None


class ConceptGraph(BaseModel):
    nodes: list[ConceptNode]
    edges: list[ConceptEdge]


class QueryResponse(BaseModel):
    answer: str
    chunks: list[DocumentChunk]
    graph: ConceptGraph | None = None
    processing_time_ms: float
    cost_cents: float
    cached: bool = False


class HealthResponse(BaseModel):
    status: str
    neo4j_connected: bool
    redis_connected: bool
    timestamp: datetime


class IngestRequest(BaseModel):
    file_paths: list[str] = Field(..., min_length=1)
    course_name: str | None = None
    overwrite: bool = False


class IngestResponse(BaseModel):
    files_processed: int
    chunks_created: int
    concepts_extracted: int
    processing_time_ms: float
    errors: list[str] = Field(default_factory=list)
