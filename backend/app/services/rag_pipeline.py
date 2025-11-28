"""RAG pipeline orchestrating retrieval, reranking, and generation."""

import time
from anthropic import AsyncAnthropic

from app.core.config import get_settings
from app.core.exceptions import RAGPipelineError
from app.core.logging import get_logger
from app.models.schemas import ConceptGraph, DocumentChunk, QueryResponse
from app.services.embeddings import EmbeddingService
from app.services.neo4j_client import Neo4jClient

logger = get_logger(__name__)


class RAGPipeline:
    """Orchestrates the full RAG query pipeline."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        neo4j_client: Neo4jClient,
    ) -> None:
        self.settings = get_settings()
        self.embedding_service = embedding_service
        self.neo4j_client = neo4j_client
        self.claude_client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

    async def query(
        self,
        question: str,
        max_chunks: int = 5,
        include_graph: bool = True,
    ) -> QueryResponse:
        """
        Execute full RAG pipeline.

        Args:
            question: User's question
            max_chunks: Maximum chunks to use for context
            include_graph: Whether to include concept graph

        Returns:
            Complete query response with answer and metadata
        """
        start_time = time.time()

        try:
            logger.info("rag_query_started", question=question)

            # Step 1: Embed query
            query_embedding = await self.embedding_service.embed_query(question)

            # Step 2: Vector search
            retrieved_chunks = await self.neo4j_client.vector_search(
                query_embedding=query_embedding,
                limit=self.settings.max_chunks_retrieved,
            )

            # Step 3: Rerank and filter
            relevant_chunks = self._rerank_chunks(
                retrieved_chunks,
                top_k=max_chunks,
            )

            # Step 4: Generate answer with Claude
            answer = await self._generate_answer(question, relevant_chunks)

            # Step 5: Extract concepts and build graph (optional)
            graph: ConceptGraph | None = None
            if include_graph and relevant_chunks:
                graph = await self._build_concept_graph(relevant_chunks)

            # Calculate metrics
            processing_time_ms = (time.time() - start_time) * 1000
            cost_estimate = self._estimate_cost(len(relevant_chunks), len(answer))

            logger.info(
                "rag_query_complete",
                chunks_used=len(relevant_chunks),
                processing_time_ms=processing_time_ms,
                cost_cents=cost_estimate,
            )

            return QueryResponse(
                answer=answer,
                chunks=relevant_chunks,
                graph=graph,
                processing_time_ms=processing_time_ms,
                cost_estimate_cents=cost_estimate,
            )

        except Exception as e:
            logger.error("rag_query_failed", error=str(e))
            raise RAGPipelineError(f"RAG pipeline failed: {str(e)}") from e

    def _rerank_chunks(
        self,
        chunks: list[DocumentChunk],
        top_k: int,
    ) -> list[DocumentChunk]:
        """
        Rerank chunks by relevance score and apply threshold.

        Args:
            chunks: Retrieved chunks
            top_k: Number of top chunks to keep

        Returns:
            Filtered and reranked chunks
        """
        # Filter by relevance threshold
        relevant = [
            chunk for chunk in chunks
            if chunk.metadata.relevance_score
            and chunk.metadata.relevance_score >= self.settings.relevance_threshold
        ]

        # Sort by score descending
        relevant.sort(
            key=lambda x: x.metadata.relevance_score or 0.0,
            reverse=True,
        )

        # Take top K
        return relevant[:top_k]

    async def _generate_answer(
        self,
        question: str,
        chunks: list[DocumentChunk],
    ) -> str:
        """
        Generate answer using Claude with anti-hallucination prompt.

        Args:
            question: User's question
            chunks: Retrieved context chunks

        Returns:
            Generated answer
        """
        if not chunks:
            return "I couldn't find any relevant information in your notes to answer this question."

        # Build context from chunks
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source = f"{chunk.metadata.course or 'Unknown'}"
            if chunk.metadata.lecture:
                source += f" - {chunk.metadata.lecture}"
            if chunk.metadata.page_num:
                source += f" (Page {chunk.metadata.page_num})"

            context_parts.append(f"[Source {i}: {source}]\n{chunk.content}\n")

        context = "\n---\n".join(context_parts)

        # Anti-hallucination prompt (from the blog post)
        prompt = f"""You are an AI assistant helping a student understand their course notes.

Answer the following question using ONLY the information provided in the context below.

IMPORTANT RULES:
- Only use information explicitly stated in the context
- If the context doesn't contain enough information, say "I couldn't find enough information in your notes to answer this question"
- Cite which source(s) you're using (e.g., "According to Source 1...")
- Do not add information from your general knowledge
- Be concise but complete

Context from notes:
{context}

Question: {question}

Answer:"""

        try:
            response = await self.claude_client.messages.create(
                model=self.settings.claude_model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            answer = response.content[0].text

            logger.debug(
                "answer_generated",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

            return answer

        except Exception as e:
            logger.error("claude_generation_failed", error=str(e))
            raise RAGPipelineError(f"Failed to generate answer: {str(e)}") from e

    async def _build_concept_graph(
        self,
        chunks: list[DocumentChunk],
    ) -> ConceptGraph | None:
        """
        Build concept graph from retrieved chunks.

        Args:
            chunks: Retrieved document chunks

        Returns:
            Concept graph or None if extraction fails
        """
        # Extract unique concepts from chunk metadata
        # In a full implementation, we'd extract concepts via Claude here
        # For now, we'll return a simple graph based on courses/topics

        try:
            # This is a placeholder - you'd want to extract concepts properly
            # using Claude to analyze the chunk content
            concepts = set()
            for chunk in chunks:
                if chunk.metadata.course:
                    concepts.add(chunk.metadata.course)
                if chunk.metadata.topic:
                    concepts.add(chunk.metadata.topic)

            # For now, return None - proper implementation would query Neo4j
            # for the concept neighborhood
            return None

        except Exception as e:
            logger.warning("graph_building_failed", error=str(e))
            return None

    def _estimate_cost(self, num_chunks: int, answer_length: int) -> float:
        """
        Estimate API cost in cents.

        Args:
            num_chunks: Number of chunks used
            answer_length: Length of generated answer

        Returns:
            Estimated cost in cents
        """
        # Rough estimates (actual costs vary):
        # - Embedding: ~$0.02 per 1M tokens (~$0.00002 per query)
        # - Claude Sonnet: ~$3/$15 per 1M tokens (input/output)

        embedding_cost = 0.00002  # negligible

        # Estimate tokens (very rough: 1 token ≈ 4 chars)
        input_tokens = sum(len(c.content) for c in []) + len("") // 4  # chunks + prompt
        output_tokens = answer_length // 4

        claude_cost = (input_tokens * 3 / 1_000_000) + (output_tokens * 15 / 1_000_000)

        total_cents = (embedding_cost + claude_cost) * 100
        return round(total_cents, 4)
