import hashlib
import json
import re
import time

from anthropic import AsyncAnthropic
from cohere import AsyncClient as CohereClient

from app.core.config import get_settings
from app.core.exceptions import RAGPipelineError
from app.core.logging import get_logger
from app.models.schemas import Citation, ConceptGraph, DocumentChunk, QueryResponse
from app.services.embeddings import EmbeddingService
from app.services.neo4j_client import Neo4jClient

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are an AI assistant helping a student understand their course notes.

IMPORTANT RULES:
- Only use information explicitly stated in the context
- If the context doesn't contain enough information, say so clearly
- Do not add information from your general knowledge
- Be concise but complete

CITATIONS:
- You MUST call the answer_with_citations tool to respond
- For each claim in your answer, include a citation with the chunk_id of the source
- Each citation's quote must be a verbatim span copied from that chunk
- Use the exact chunk_id strings shown in the context headers

FORMATTING:
- Use markdown for structure: **bold**, *italics*, lists, headings, etc.
- Use LaTeX for math: inline $x^2$ and display $$\\sum_{{i=1}}^n x_i$$
- Use code blocks with language tags for code snippets"""

_USER_PROMPT = """Answer the following question using ONLY the information provided in the context below.

Context from notes:
{context}

Question: {question}"""

_ANSWER_TOOL = {
    "name": "answer_with_citations",
    "description": (
        "Produce an answer grounded in the provided context. For every claim, "
        "include a citation with the chunk_id of the source chunk and a verbatim "
        "quote from that chunk."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "description": (
                    "The answer to the question, in markdown. Reference sources "
                    "inline by their chunk_id in parentheses where relevant."
                ),
            },
            "citations": {
                "type": "array",
                "description": "Citations supporting the answer.",
                "items": {
                    "type": "object",
                    "properties": {
                        "chunk_id": {
                            "type": "string",
                            "description": (
                                "The chunk_id of the supporting chunk. Must be one "
                                "of the chunk_ids shown in the context headers."
                            ),
                        },
                        "quote": {
                            "type": "string",
                            "description": (
                                "A verbatim span copied from the cited chunk that "
                                "supports the claim."
                            ),
                        },
                    },
                    "required": ["chunk_id", "quote"],
                },
            },
        },
        "required": ["answer", "citations"],
    },
}


class RAGPipeline:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        neo4j_client: Neo4jClient,
    ) -> None:
        self.settings = get_settings()
        self.embedding_service = embedding_service
        self.neo4j_client = neo4j_client
        self.claude_client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)
        self.cohere_client = CohereClient(api_key=self.settings.cohere_api_key)

    async def query(
        self,
        question: str,
        max_chunks: int = 5,
        include_graph: bool = True,
    ) -> QueryResponse:
        start_time = time.time()

        try:
            logger.info("rag_query_started", question=question)

            # Check response cache first
            cache_key = self._response_cache_key(question, max_chunks, include_graph)
            cached = await self._get_cached_response(cache_key)
            if cached:
                cached.cached = True
                cached.processing_time_ms = (time.time() - start_time) * 1000
                cached.cost_cents = 0.0
                logger.info("rag_query_cache_hit", question=question)
                return cached

            query_embedding, embedding_tokens = await self.embedding_service.embed_query(question)

            retrieved_chunks = await self.neo4j_client.vector_search(
                query_embedding=query_embedding,
                limit=self.settings.max_chunks_retrieved,
            )

            relevant_chunks = await self._rerank_chunks(
                question, retrieved_chunks, top_k=max_chunks,
            )
            answer, raw_citations, input_tokens, output_tokens = await self._generate_answer(
                question, relevant_chunks,
            )
            citations = self._validate_citations(raw_citations, relevant_chunks)

            graph: ConceptGraph | None = None
            if include_graph and relevant_chunks:
                graph = await self._build_concept_graph(relevant_chunks)

            processing_time_ms = (time.time() - start_time) * 1000
            cost_cents = self._calculate_cost(embedding_tokens, input_tokens, output_tokens)

            logger.info(
                "rag_query_complete",
                chunks_used=len(relevant_chunks),
                citations_kept=len(citations),
                citations_dropped=len(raw_citations) - len(citations),
                processing_time_ms=processing_time_ms,
                cost_cents=cost_cents,
            )

            response = QueryResponse(
                answer=answer,
                citations=citations,
                chunks=relevant_chunks,
                graph=graph,
                processing_time_ms=processing_time_ms,
                cost_cents=cost_cents,
            )

            # Cache the response
            await self._cache_response(cache_key, response)

            return response

        except Exception as e:
            logger.error("rag_query_failed", error=str(e))
            raise RAGPipelineError(f"RAG pipeline failed: {e}") from e

    async def _rerank_chunks(
        self,
        query: str,
        chunks: list[DocumentChunk],
        top_k: int,
    ) -> list[DocumentChunk]:
        if not chunks:
            return []

        try:
            rerank_response = await self.cohere_client.rerank(
                model="rerank-v3.5",
                query=query,
                documents=[chunk.content for chunk in chunks],
                top_n=min(top_k, len(chunks)),
            )

            reranked: list[DocumentChunk] = []
            for result in rerank_response.results:
                chunk = chunks[result.index]
                chunk.metadata.relevance_score = result.relevance_score
                reranked.append(chunk)

            return reranked

        except Exception as e:
            # Fallback: filter by threshold and sort by existing score
            logger.warning("cohere_rerank_failed_using_fallback", error=str(e))

            relevant = [
                c for c in chunks
                if c.metadata.relevance_score
                and c.metadata.relevance_score >= self.settings.relevance_threshold
            ]
            relevant.sort(key=lambda x: x.metadata.relevance_score or 0.0, reverse=True)
            return relevant[:top_k]

    async def _generate_answer(
        self,
        question: str,
        chunks: list[DocumentChunk],
    ) -> tuple[str, list[Citation], int, int]:
        if not chunks:
            return (
                "I couldn't find any relevant information in your notes to answer this question.",
                [],
                0,
                0,
            )

        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.metadata.course or "Unknown"
            if chunk.metadata.lecture:
                source += f" - {chunk.metadata.lecture}"
            if chunk.metadata.page_num:
                source += f" (Page {chunk.metadata.page_num})"
            header = f"[Source {i} | chunk_id={chunk.metadata.chunk_id} | {source}]"
            context_parts.append(f"{header}\n{chunk.content}\n")

        user_prompt = _USER_PROMPT.format(
            context="\n---\n".join(context_parts),
            question=question,
        )

        try:
            response = await self.claude_client.messages.create(
                model=self.settings.claude_model,
                max_tokens=1024,
                system=[{
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                tools=[_ANSWER_TOOL],
                tool_choice={"type": "tool", "name": "answer_with_citations"},
                messages=[{"role": "user", "content": user_prompt}],
            )
            answer, citations = self._parse_tool_response(response)
            return (
                answer,
                citations,
                response.usage.input_tokens,
                response.usage.output_tokens,
            )
        except RAGPipelineError:
            raise
        except Exception as e:
            raise RAGPipelineError(f"Failed to generate answer: {e}") from e

    @staticmethod
    def _parse_tool_response(response) -> tuple[str, list[Citation]]:
        """Extract the answer and raw (unvalidated) citations from a tool-use response."""
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "answer_with_citations":
                payload = block.input or {}
                answer = payload.get("answer", "").strip()
                raw_citations: list[Citation] = []
                for item in payload.get("citations") or []:
                    try:
                        raw_citations.append(Citation.model_validate(item))
                    except Exception as e:
                        logger.warning("citation_parse_failed", item=item, error=str(e))
                return answer, raw_citations

        raise RAGPipelineError("Claude did not call answer_with_citations tool")

    @staticmethod
    def _validate_citations(
        citations: list[Citation],
        retrieved_chunks: list[DocumentChunk],
    ) -> list[Citation]:
        """Drop citations whose chunk_id was not retrieved, or whose quote is not in that chunk.

        Two-layer hallucination guard:
        1. chunk_id must be in the retrieved set (Claude cannot invent ids)
        2. quote must appear in the cited chunk's text (case + whitespace normalized)
        """
        chunks_by_id = {c.metadata.chunk_id: c for c in retrieved_chunks}
        kept: list[Citation] = []
        for citation in citations:
            chunk = chunks_by_id.get(citation.chunk_id)
            if chunk is None:
                logger.warning(
                    "citation_hallucinated_chunk_id",
                    cited_chunk_id=citation.chunk_id,
                    quote_preview=citation.quote[:80],
                )
                continue
            if not RAGPipeline._quote_in_chunk(citation.quote, chunk.content):
                logger.warning(
                    "citation_quote_not_in_chunk",
                    cited_chunk_id=citation.chunk_id,
                    quote_preview=citation.quote[:80],
                )
                continue
            kept.append(citation)
        return kept

    @staticmethod
    def _quote_in_chunk(quote: str, chunk_text: str) -> bool:
        """Case-insensitive, whitespace-normalized substring check.

        LLMs sometimes tweak whitespace or capitalization when quoting.
        We normalize both sides before comparison to reduce false negatives
        while still catching outright fabrications.
        """
        def normalize(s: str) -> str:
            return re.sub(r"\s+", " ", s).strip().lower()

        return normalize(quote) in normalize(chunk_text)

    async def _build_concept_graph(
        self,
        chunks: list[DocumentChunk],
    ) -> ConceptGraph | None:
        try:
            chunk_ids = [chunk.metadata.chunk_id for chunk in chunks]
            concept_names = await self.neo4j_client.get_concepts_for_chunks(chunk_ids)

            if not concept_names:
                return None

            nodes_dict: dict[str, dict] = {}
            all_edges: list[dict] = []

            for concept_name in concept_names[:5]:
                try:
                    subgraph = await self.neo4j_client.get_concept_graph(concept_name, depth=1)

                    for node in subgraph.nodes:
                        if node.name not in nodes_dict:
                            nodes_dict[node.name] = {
                                "name": node.name,
                                "node_type": node.node_type,
                                "description": node.description,
                            }

                    for edge in subgraph.edges:
                        all_edges.append({
                            "source": edge.source,
                            "target": edge.target,
                            "edge_type": edge.edge_type,
                            "weight": edge.weight,
                        })
                except Exception as e:
                    logger.warning("concept_subgraph_failed", concept=concept_name, error=str(e))
                    continue

            # Deduplicate edges by (source, target, type)
            seen: set[tuple[str, str, str]] = set()
            unique_edges = []
            for e in all_edges:
                key = (e["source"], e["target"], e["edge_type"])
                if key not in seen:
                    seen.add(key)
                    unique_edges.append(e)

            from app.models.schemas import ConceptEdge, ConceptNode

            return ConceptGraph(
                nodes=[ConceptNode(**data) for data in nodes_dict.values()],
                edges=[ConceptEdge(**data) for data in unique_edges],
            )

        except Exception as e:
            logger.warning("graph_building_failed", error=str(e))
            return None

    def _calculate_cost(
        self,
        embedding_tokens: int,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Cost in cents. Pricing: OpenAI embed $0.02/1M, Claude Sonnet $3/$15 per 1M in/out."""
        embedding_cost = (embedding_tokens / 1_000_000) * 0.02
        claude_input_cost = (input_tokens / 1_000_000) * 3.0
        claude_output_cost = (output_tokens / 1_000_000) * 15.0
        return round((embedding_cost + claude_input_cost + claude_output_cost) * 100, 4)

    # --- Response caching ---

    def _response_cache_key(self, question: str, max_chunks: int, include_graph: bool) -> str:
        content = f"{question}:{max_chunks}:{include_graph}"
        return f"resp:{hashlib.sha256(content.encode()).hexdigest()}"

    async def _get_cached_response(self, cache_key: str) -> QueryResponse | None:
        redis = self.embedding_service.redis_client
        if not redis:
            return None
        try:
            data = await redis.get(cache_key)
            if data:
                return QueryResponse.model_validate_json(data)
        except Exception as e:
            logger.warning("response_cache_read_failed", error=str(e))
        return None

    async def _cache_response(self, cache_key: str, response: QueryResponse) -> None:
        redis = self.embedding_service.redis_client
        if not redis:
            return
        try:
            await redis.setex(
                cache_key,
                self.settings.response_cache_ttl,
                response.model_dump_json(),
            )
        except Exception as e:
            logger.warning("response_cache_write_failed", error=str(e))
