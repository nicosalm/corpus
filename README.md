# Corpus - RAG-Powered Knowledge Graph

RAG system that turns your personal notes into a queryable knowledge graph.

## Architecture

**Backend**: FastAPI (Python 3.11+)
**Vector + Graph DB**: Neo4j with vector search
**Cache**: Redis
**Embeddings**: OpenAI `text-embedding-3-small`
**LLM**: Claude Sonnet 4.5
**TTS**: Fish.audio (planned)
**Frontend**: Svelte (planned)

## Features

- **PDF Ingestion**: Chunks text, extracts metadata (course, lecture, page)
- **Vector Search**: Semantic similarity search via Neo4j
- **Knowledge Graph**: Links concepts across notes
- **RAG Pipeline**: Answers questions using only your notes (no hallucinations)
- **Caching**: Saves embeddings in Redis to cut costs
- **Logging**: Structured JSON logs for debugging

## Project Structure

```
corpus/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes
│   │   ├── core/         # Config, logging, exceptions
│   │   ├── models/       # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   └── main.py       # Application entry
│   ├── tests/            # Unit & integration tests
│   ├── pyproject.toml    # Dependencies (uv)
│   └── Dockerfile
├── data/
│   ├── raw/              # Your PDFs go here
│   └── processed/        # Processed chunks
├── scripts/
│   └── ingest_pdfs.py    # Batch ingestion script
└── docker-compose.yml
```

## Setup

### Prerequisites

- Docker & Docker Compose
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- API keys:
  - Anthropic (Claude)
  - OpenAI (Embeddings)
  - Fish.audio (for TTS, optional)

### Installation

1. **Clone and setup environment**:
```bash
cd corpus
cp .env.example .env
# Edit .env with your API keys
```

2. **Start services with Docker**:
```bash
docker-compose up -d
```

This starts:
- FastAPI backend (`:8000`)
- Neo4j (`:7474` browser, `:7687` bolt)
- Redis (`:6379`)

3. **Verify services**:
```bash
curl http://localhost:8000/health
```

### Local Development (without Docker)

```bash
cd backend

# Install dependencies
uv pip install -e ".[dev]"

# Start Neo4j and Redis separately, then:
uvicorn app.main:app --reload
```

## Usage

### 1. Ingest PDFs

Place your PDFs in `data/raw/`:

```bash
cp ~/Documents/CS331_Notes.pdf data/raw/
```

Run ingestion:

```bash
python scripts/ingest_pdfs.py
```

Or via API:

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": ["/data/raw/CS331_Notes.pdf"],
    "overwrite": false
  }'
```

### 2. Query the Knowledge Base

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Explain dynamic programming",
    "max_chunks": 5,
    "include_graph": true
  }'
```

### 3. Explore Concept Graph

```bash
# Get graph neighborhood around a concept
curl http://localhost:8000/graph/dynamic%20programming?depth=2
```

Returns nodes and edges for visualization (D3/Cytoscape).

### 4. Explore API

Visit http://localhost:8000/docs for interactive API documentation (Swagger UI).

## Configuration

Edit `.env` to customize:

```bash
# Chunking
CHUNK_SIZE=800                # Target chunk size
CHUNK_OVERLAP=100             # Overlap between chunks

# RAG
MAX_CHUNKS_RETRIEVED=20       # Initial retrieval limit
RERANK_TOP_K=5                # Chunks after reranking
RELEVANCE_THRESHOLD=0.5       # Minimum similarity score

# Models
EMBEDDING_MODEL=text-embedding-3-small
```

## Testing

```bash
cd backend

# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_pdf_processor.py
```

## Status

**Phase 1: Backend Foundation ✅**
- PDF ingestion, chunking, embeddings
- Vector search + RAG query pipeline
- Docker setup with Neo4j + Redis
- 4 API endpoints, tests passing

**Phase 2: Enhanced RAG (Next)**
- Concept extraction (currently stubbed in `rag_pipeline.py:118`)
- Proper reranking with Cohere (using simple score filter now)
- Actual cost tracking from API responses
- Conversation history and context tracking

**Phase 3: Frontend**
- Svelte web app
- Chat interface
- Interactive graph visualization (D3/Cytoscape/svelvet)
- Fish.audio TTS integration
- Voice input

## Known Limitations

- **No OCR**: Handwritten notes won't work (digital text PDFs only)
- **Concept extraction stubbed**: Graph endpoints return empty until implemented
- **Simple reranking**: Using cosine similarity filtering instead of proper reranking model
- **No rate limiting**: API endpoints are unprotected
- **No conversation context**: Each query is independent

## Architecture Decisions

Based on [Vectorize RAG Best Practices](https://vectorize.io/blog/creating-a-context-sensitive-ai-assistant-lessons-from-building-a-rag-application):

1. **Semantic Chunking**: 500-1000 token chunks with 50-100 token overlap
2. **Reranking**: Filter retrieval results to prevent hallucinations
3. **Anti-Hallucination Prompting**: Explicit instructions to cite sources
4. **Relevance Threshold**: Discard low-scoring chunks (< 0.5)
5. **Context-Sensitive Retrieval**: Metadata-enriched queries

## Cost Estimates

Per 1000 queries (assuming 5 chunks, 200-word answers):

- **Embeddings**: ~$0.02 (cached after first query)
- **Claude**: ~$1.50
- **Total**: ~$1.52/1000 queries

Redis caching reduces embedding costs by ~95% after initial ingestion.
