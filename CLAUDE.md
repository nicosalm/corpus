# Claude Context: Corpus RAG Project

## Project Overview

**Goal**: Build a RAG system that converts personal undergrad notes (PDFs) into a queryable knowledge graph with graph visualization frontend.

**Stack**:
- Backend: FastAPI + Python 3.11 (uv via Docker)
- Vector + Graph DB: Neo4j 5.15-enterprise with vector search + APOC
- Cache: Redis 7-alpine
- Embeddings: OpenAI `text-embedding-3-small` (1536d, $0.02/1M tokens)
- LLM: Anthropic Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`)
- Frontend: Svelte (not started)
- TTS: Fish.audio (planned, not implemented)

**Input**: Digital text PDFs (LaTeX notes, typed Notability exports)
**Output**: Q&A with cited sources + interactive concept graph

## Current State: Phase 1 Complete & Tested ✅

**Last Updated**: 2025-11-28

**Status**: Fully operational RAG system with 57 chunks ingested from Unit_3_532.pdf

### What's Built and Working

**Core Services** (`backend/app/services/`):
1. `pdf_processor.py` - PyMuPDF extraction + LangChain RecursiveCharacterTextSplitter
   - Chunks: 800 tokens, 100 overlap
   - Extracts course/lecture from filename (regex: `CS331_Lecture12.pdf`)
   - Preserves page numbers
2. `embeddings.py` - OpenAI embeddings with Redis caching + tenacity retries
3. `neo4j_client.py` - Async driver, vector search, graph queries
   - Vector index: `chunk_embeddings` (cosine similarity)
   - Cypher queries for RELATES_TO relationships
4. `rag_pipeline.py` - Full retrieval → rerank → Claude generation
   - Anti-hallucination prompting (from Vectorize blog)
   - Relevance threshold: 0.5

**API Endpoints** (`backend/app/api/routes/`):
- `POST /query` - RAG query (question → answer + chunks + optional graph)
- `POST /ingest` - Trigger PDF processing pipeline
- `GET /health` - Neo4j + Redis health check
- `GET /graph/{concept}?depth=2` - Get concept neighborhood

**Infrastructure**:
- `docker-compose.yml` - FastAPI + Neo4j + Redis (with health checks)
- Pydantic models in `app/models/{schemas,domain}.py`
- Structured logging via `structlog` (JSON in prod, pretty in dev)
- Config via `pydantic-settings` (reads `.env`)
- Pytest suite with fixtures (`tests/conftest.py`, unit + integration)
- uv-based Dockerfile using official `ghcr.io/astral-sh/uv` image

**Verified Working**:
- ✅ PDF ingestion: 57 chunks from Unit_3_532.pdf (26 pages, 31,942 chars)
- ✅ Embeddings: OpenAI API with Redis caching (57 successful calls)
- ✅ Neo4j storage: All chunks stored with 1536d vectors
- ✅ Query pipeline: Tested with "K-Means algorithm" and "PCA" queries
- ✅ Claude responses: Proper citations, anti-hallucination working
- ✅ Cost tracking: ~$0.001-0.004 per query
- ✅ Health checks: All services passing

### What's Stubbed/Incomplete

**Critical Gaps**:
1. **Concept Extraction** (`rag_pipeline.py:118`) - `_build_concept_graph()` returns `None`
   - Should: Extract concepts from chunks via Claude
   - Should: Store in Neo4j as `(Concept)-[:MENTIONED_IN]->(Chunk)`
   - Should: Create `RELATES_TO` edges between co-occurring concepts
2. **Reranking** (`rag_pipeline.py:72`) - Simple score filtering only
   - Should: Use Cohere rerank API or cross-encoder
   - Currently: Just sorts by cosine similarity
3. **Cost Tracking** (`rag_pipeline.py:213`) - Rough estimation
   - Should: Track actual token counts from API responses
4. **Graph Relationships** - No automatic concept linking yet
   - Neo4j schema supports it, but ingestion doesn't populate

**Missing Features** (not blocking):
- OCR for handwritten notes (future)
- Conversation context/history
- Rate limiting middleware
- Frontend (Svelte app)
- Fish.audio TTS integration

## Architecture Decisions

### Why This Stack?

1. **Neo4j over dedicated vector DB**: Dual capability (vector search + graph), single DB
2. **FastAPI over Flask**: Async for parallel API calls (embed + search + LLM)
3. **OpenAI embeddings + Claude LLM**: Anthropic doesn't have embeddings; Claude better at constrained generation
4. **Redis caching**: Saves ~95% embedding costs on repeated queries

### RAG Pipeline Flow

```
User Question
  ↓
1. Embed query (OpenAI, cached)
  ↓
2. Vector search (Neo4j, top 20 chunks)
  ↓
3. Rerank (simple score filter → should be Cohere)
  ↓
4. Build context from top 5 chunks
  ↓
5. Prompt Claude with anti-hallucination rules
  ↓
6. Return answer + chunks + concept graph
```

### Key Patterns Used

- **Dependency Injection**: Global service instances in `app/api/dependencies.py`
  - Initialized in `main.py` lifespan context
  - Injected via FastAPI `Depends()`
- **Error Handling**: Custom exceptions in `app/core/exceptions.py`
  - Caught at route level, logged, returned as HTTPException
- **Async Everywhere**: All services use `async/await`
- **Retries**: `@retry` decorator from tenacity on API calls
- **Logging**: `structlog` with contextual fields (e.g., `chunk_id`, `cost_cents`)

## File Navigation

### Critical Files

**Entry Point**:
- `backend/app/main.py` - FastAPI app, lifespan (connect/disconnect services)

**Core Logic**:
- `backend/app/services/rag_pipeline.py` - **START HERE** for RAG flow
- `backend/app/services/neo4j_client.py` - Database operations
- `backend/app/services/pdf_processor.py` - Chunking logic

**Configuration**:
- `.env.example` - All environment variables
- `backend/app/core/config.py` - Settings schema
- `docker-compose.yml` - Service orchestration

**Data Models**:
- `backend/app/models/schemas.py` - API request/response models
- `backend/app/models/domain.py` - Internal domain models

### Where to Add Features

**New API endpoint**:
1. Create `backend/app/api/routes/your_route.py`
2. Import and add to `main.py`: `app.include_router(your_route.router)`

**New service**:
1. Create `backend/app/services/your_service.py`
2. Add to `dependencies.py` for injection
3. Initialize in `main.py` lifespan

**Concept extraction**:
- Modify `rag_pipeline.py:_build_concept_graph()`
- Add prompt to extract concepts via Claude
- Use `neo4j_client.store_concepts()` + `create_concept_relations()`

**Reranking**:
- Modify `rag_pipeline.py:_rerank_chunks()`
- Add Cohere client to `pyproject.toml`
- Call Cohere rerank API before returning top-k

## Neo4j Schema

**Nodes**:
- `Chunk`: {chunk_id, text, embedding[1536], source_file, page_num, course, lecture}
- `Concept`: {name, concept_type} (not populated yet)
- `Course`: (planned, not implemented)

**Relationships**:
- `(Concept)-[:MENTIONED_IN]->(Chunk)` (not populated yet)
- `(Concept)-[:RELATES_TO]-(Concept)` with weight (not populated yet)

**Indexes**:
- Vector index: `chunk_embeddings` on `Chunk.embedding`
- Unique constraint: `Chunk.chunk_id`, `Concept.name`

## How to Test/Run

```bash
# Start services
docker-compose up -d

# Check health
curl http://localhost:8000/health

# Ingest PDFs (via API - recommended)
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"file_paths": ["/data/raw/Unit_3_532.pdf"]}'

# Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain the K-Means algorithm", "max_chunks": 5}'

# Explore graph (will be empty until concept extraction works)
curl http://localhost:8000/graph/dynamic%20programming?depth=2

# Neo4j browser
open http://localhost:7474
# Login: neo4j / corpus_secure_password_2025

# API docs
open http://localhost:8000/docs

# Run tests (local only, requires uv install)
cd backend && pytest
```

## Next Steps (Priority Order)

### Immediate (Phase 2):
1. **Implement concept extraction**:
   - In `rag_pipeline.py:_build_concept_graph()`
   - Prompt Claude to extract concepts from each chunk
   - Store via `neo4j_client.store_concepts()`
   - Build co-occurrence edges
2. **Add Cohere reranking**:
   - `uv pip install cohere`
   - Replace `_rerank_chunks()` with Cohere API call
   - Keep relevance threshold fallback
3. **Fix cost tracking**:
   - Parse token counts from Claude/OpenAI responses
   - Log actual costs, not estimates

### Medium Term (Phase 3):
4. **Svelte Frontend**:
   - Create `frontend/` directory
   - Chat UI (text input → display answer)
   - Graph viz with D3/Cytoscape (consume `/graph/{concept}`)
   - Connect to Fish.audio for TTS
5. **Deploy**:
   - Backend: fly.io or Railway
   - Frontend: Cloudflare Pages
   - Neo4j: Neo4j Aura (managed)

### Later (Phase 4):
6. OCR support for handwritten notes
7. Multi-user auth
8. Conversation history/context

## Gotchas & Known Issues

1. **Neo4j License**: Using Enterprise in docker-compose for vector search. License accepted via env var.
2. **Empty Graphs**: `/graph/{concept}` will return 404 until concept extraction is implemented.
3. **File Paths in Ingestion**: Use paths relative to container (`/data/raw/filename.pdf` when calling API).
4. **Metadata Extraction**: Relies on filename patterns like `CS331_Lecture12.pdf`. Won't extract course from arbitrary filenames.
5. **Model Name Format**: Claude model must use hyphens: `claude-sonnet-4-5-20250929` NOT `claude-sonnet-4.5-20250929`
6. **Docker Restart**: After changing `.env`, must restart backend: `docker-compose restart backend`
7. **Scripts Mount**: `scripts/` directory requires full restart to mount: `docker-compose down && docker-compose up -d`

## Important Conventions

- **Logging**: Use `logger.info(event_name, key=value)` not string messages
- **Errors**: Raise custom exceptions from `core/exceptions.py`, catch at route level
- **Async**: All service methods are `async`, use `await`
- **Types**: Pydantic models for validation, type hints everywhere
- **Tests**: Mock external APIs (OpenAI, Anthropic, Neo4j) using pytest fixtures

## Environment Variables (from .env)

Required:
- `ANTHROPIC_API_KEY` - Claude API (configured)
- `OPENAI_API_KEY` - Embeddings (configured)
- `NEO4J_PASSWORD` - Neo4j auth (set to `corpus_secure_password_2025`)

Models:
- `CLAUDE_MODEL` - Currently `claude-sonnet-4-5-20250929` (note: hyphens not dots!)
- `EMBEDDING_MODEL` - Currently `text-embedding-3-small`

Optional:
- `FISH_AUDIO_API_KEY` - TTS (not used yet)
- `CHUNK_SIZE`, `CHUNK_OVERLAP` - Chunking params (800/100)
- `RELEVANCE_THRESHOLD` - Minimum similarity score (0.5)

## Cost Estimates

Per 1000 queries (5 chunks, 200-word answers):
- Embeddings: ~$0.02 (negligible, cached after first)
- Claude: ~$1.50
- **Total: ~$1.52/1000 queries**

## Contact Context

This is a personal project for the user's 4 years of undergrad notes. Single-user initially, may expand later.

---

**When resuming work**: Start by checking what phase user wants to work on. If continuing Phase 2, begin with concept extraction in `rag_pipeline.py`.
