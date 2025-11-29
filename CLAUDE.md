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

## Current State: Phase 2 Complete & Tested ✅

**Last Updated**: 2025-11-29

**Status**: Fully operational RAG system with concept extraction, accurate cost tracking, and Cohere reranking

### What's Built and Working

**Core Services** (`backend/app/services/`):
1. `pdf_processor.py` - PyMuPDF extraction + LangChain RecursiveCharacterTextSplitter
   - Chunks: 800 tokens, 100 overlap
   - Extracts course/lecture from filename (regex: `CS331_Lecture12.pdf`)
   - Preserves page numbers
2. `embeddings.py` - OpenAI embeddings with Redis caching + token tracking
   - Returns (embedding, tokens_used) tuples for cost tracking
   - Redis cache saves ~95% costs on repeat queries
3. `neo4j_client.py` - Async driver, vector search, graph queries
   - Vector index: `chunk_embeddings` (cosine similarity)
   - Cypher queries for RELATES_TO relationships
   - `get_concepts_for_chunks()` for graph building
4. `rag_pipeline.py` - Full retrieval → Cohere rerank → Claude generation
   - **Cohere rerank-v3.5** with fallback to score filtering
   - Anti-hallucination prompting (from Vectorize blog)
   - Accurate cost tracking from API token counts
5. `concept_extractor.py` - Claude-powered concept extraction **NEW**
   - Extracts 6 concept types: algorithm, topic, theory, technique, term, person
   - JSON-structured output with confidence scores
   - ~6-7 concepts per chunk average

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
- ✅ Embeddings: OpenAI API with Redis caching + token tracking
- ✅ Neo4j storage: Chunks + 372 concepts with relationships
- ✅ Concept extraction: ~6.5 concepts/chunk, ~8min processing
- ✅ Query pipeline: Tested with PCA, K-Means queries
- ✅ Cohere reranking: Semantic relevance scoring working
- ✅ Accurate cost tracking: $0.007866 per query (not estimate!)
- ✅ Graph visualization: `/graph/{concept}` endpoint functional
- ✅ Health checks: All services passing

### What's Complete (Phase 2) ✅

1. **Concept Extraction** - Fully implemented
   - Extracts concepts via Claude during ingestion
   - Stores in Neo4j as `(Concept)-[:MENTIONED_IN]->(Chunk)`
   - Creates `RELATES_TO` edges for chunk-level co-occurrence
   - Weights increment when concepts appear together multiple times

2. **Cohere Reranking** - Production ready
   - Uses `rerank-v3.5` multilingual model
   - Graceful fallback to score filtering if API fails
   - Significant relevance improvements over vector search alone

3. **Accurate Cost Tracking** - Real-time tracking
   - Tracks actual tokens from OpenAI & Claude APIs
   - Pricing: $0.02/1M (embeddings), $3/$15/1M (Claude)
   - Typical query: $0.007-0.012

**Missing Features** (Phase 3+):
- Frontend (Svelte app with graph visualization)
- Fish.audio TTS integration
- Conversation context/history
- OCR for handwritten notes
- Rate limiting middleware
- Multi-user auth

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
1. Embed query (OpenAI, cached) → track tokens
  ↓
2. Vector search (Neo4j, top 20 chunks)
  ↓
3. Cohere rerank (semantic relevance, top 5) → with fallback
  ↓
4. Build context from top 5 chunks
  ↓
5. Prompt Claude with anti-hallucination rules → track tokens
  ↓
6. Build concept graph from stored concepts (optional)
  ↓
7. Calculate actual cost → return answer + chunks + graph + cost
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

### ✅ Completed (Phase 2):
1. **Concept extraction** - DONE
   - Claude-powered extraction in `concept_extractor.py`
   - Stores 6 concept types with confidence scores
   - Chunk-level co-occurrence relationships
2. **Cohere reranking** - DONE
   - `rerank-v3.5` multilingual model
   - Graceful fallback to score filtering
3. **Accurate cost tracking** - DONE
   - Real token counts from API responses
   - Current pricing: $0.007-0.012/query

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
- `ANTHROPIC_API_KEY` - Claude API for generation & concept extraction
- `OPENAI_API_KEY` - Embeddings API
- `COHERE_API_KEY` - Reranking API (Phase 2)
- `NEO4J_PASSWORD` - Neo4j auth (set to `corpus_secure_password_2025`)

Models:
- `CLAUDE_MODEL` - Currently `claude-sonnet-4-5-20250929` (note: hyphens not dots!)
- `EMBEDDING_MODEL` - Currently `text-embedding-3-small`

Optional:
- `FISH_AUDIO_API_KEY` - TTS (not used yet)
- `CHUNK_SIZE`, `CHUNK_OVERLAP` - Chunking params (800/100)
- `RELEVANCE_THRESHOLD` - Minimum similarity score (0.5)

## Cost Estimates (Phase 2 - Actual Tracking)

Per Query (5 chunks, 200-word answer):
- Embeddings: $0.000002 (cached after first query)
- Cohere Reranking: Free tier (or ~$0.002)
- Claude Generation: $0.005-0.010
- **Total: ~$0.007-0.012 per query**

Per 1000 queries: **$7-12** (with caching)

One-Time Ingestion (per PDF):
- Embeddings: Cached after first run
- Concept Extraction: ~$0.50 for 57 chunks (Unit_3 example)
- **Total: ~$0.50 per document**

## Contact Context

This is a personal project for the user's 4 years of undergrad notes. Single-user initially, may expand later.

---

**When resuming work**: Start by checking what phase user wants to work on. If continuing Phase 2, begin with concept extraction in `rag_pipeline.py`.

---

## Phase 2 Implementation Details

### Task 1: Accurate Cost Tracking ✅

**Files Modified:**
- `backend/app/services/embeddings.py` - Returns `(embedding, tokens)` tuples
- `backend/app/services/rag_pipeline.py` - Tracks actual Claude token usage
- `backend/app/models/schemas.py` - Renamed `cost_estimate_cents` → `cost_cents`

**Implementation:**
- OpenAI API returns `usage.total_tokens` for embeddings
- Claude API returns `usage.input_tokens` and `usage.output_tokens`
- Calculate cost: `(embedding_tokens × $0.02 + input_tokens × $3 + output_tokens × $15) / 1M`

**Verified Result:** $0.007866 per query (actual, not estimated)

### Task 2: Cohere Reranking ✅

**Files Modified:**
- `backend/pyproject.toml` - Added `cohere>=5.11.0`
- `backend/app/services/rag_pipeline.py` - Implemented `_rerank_chunks()` with Cohere
- `backend/app/core/config.py` + `.env.example` - Added `COHERE_API_KEY`
- `docker-compose.yml` - Pass env var to container

**Implementation:**
- Uses `rerank-v3.5` multilingual model
- Graceful fallback to score-based filtering on API failure
- Updates chunk relevance scores with Cohere's semantic ranking

### Task 3: Concept Extraction ✅

**New File:**
- `backend/app/services/concept_extractor.py` - Claude-powered extraction

**Files Modified:**
- `backend/app/api/routes/ingest.py` - Integration into ingestion pipeline
- `backend/app/services/neo4j_client.py` - Added `get_concepts_for_chunks()`
- `backend/app/services/rag_pipeline.py` - Fixed `_build_concept_graph()`
- `backend/app/api/dependencies.py` + `backend/app/main.py` - DI setup

**Implementation:**
- Extracts 6 concept types: algorithm, topic, theory, technique, term, person
- JSON-structured prompts with confidence scores
- Chunk-level co-occurrence relationships (not file-level)
- Neo4j schema: `(Concept)-[:MENTIONED_IN]->(Chunk)` and `(Concept)-[:RELATES_TO {weight}]-(Concept)`

**Performance Metrics (Unit_3_532.pdf):**
- 372 concepts extracted from 57 chunks (~6.5 per chunk)
- Processing time: ~8 minutes
- Cost: ~$0.50 (one-time per document)
- Relationship weights: 4-10 (strong co-occurrence)
- Connection distribution: 19-132 per concept (meaningful clustering)

### Known Issues & Resolutions

1. **Missing COHERE_API_KEY in Docker** ✅ Fixed
   - Added to `docker-compose.yml` environment variables

2. **Over-connected graph (all weights=1)** ✅ Fixed
   - Changed from file-level to chunk-level relationships

3. **Variable reference bug in logging** ✅ Fixed
   - Removed `file_concepts` reference in `ingest.py:106`

### Testing Checklist ✅

- [x] Health endpoint returns all services healthy
- [x] PDF ingestion completes successfully (370+ concepts)
- [x] Query pipeline returns accurate costs
- [x] Cohere reranking updates relevance scores
- [x] Neo4j graph shows varied relationship weights
- [x] Graph endpoint returns concept neighborhoods
- [x] Redis caching reduces embedding costs to $0

---

**Phase 2 Status:** Complete ✅ (2025-11-29)
**Ready for Phase 3:** Frontend Development
