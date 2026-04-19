Corpus
======

> [!NOTE]
> Corpus organizes your notes as a knowledge graph. On top of vector
> search and reranking, chunks are linked through the concepts they
> share, so related material surfaces together and answers stay anchored
> to the sources that back them.

Corpus is a retrieval-augmented question-answering system for PDF notes.
It ingests documents into a Neo4j knowledge graph, embeds chunks with
OpenAI, reranks candidates with Cohere, and generates grounded answers
with the Anthropic API. A small SvelteKit frontend ships alongside the
HTTP API.

To get started, copy the example environment file and fill in your
Anthropic, OpenAI, and Cohere keys (`cp .env.example .env`), then bring
up the stack with `docker-compose up -d`. This starts the FastAPI
backend, Neo4j, and Redis. The API listens on port 8000, with a health
check at `/health` and interactive docs at `/docs`.

Drop PDFs into `data/raw/` and POST a list of paths to `/ingest`, e.g.

    curl -X POST http://localhost:8000/ingest \
        -H 'Content-Type: application/json' \
        -d '{"file_paths": ["/data/raw/notes.pdf"]}'

Files may also be uploaded directly as multipart form data via
`/ingest/upload`. Once ingestion is complete, ask questions at `/query`
with a JSON body of the form `{"question": "..."}`; the response
contains the generated answer along with citations keyed to the chunks
that supported each claim. The concept graph extracted during ingestion
can be traversed from any node with `GET /graph/{concept}?depth=N` for
N between 1 and 4.

The backend source lives under `backend/` and uses uv for dependency
management: `uv sync` creates a local `.venv`, and `uv run pytest` runs
the tests. The frontend is a standard SvelteKit app in `frontend/`;
`pnpm install` followed by `pnpm dev` will start it against the local
API.
