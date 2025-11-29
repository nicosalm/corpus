"""RAG pipeline orchestrating retrieval, reranking, and generation."""

import time
from anthropic import AsyncAnthropic
from cohere import AsyncClient as CohereClient

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
        self.cohere_client = CohereClient(api_key=self.settings.cohere_api_key)

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
            query_embedding, embedding_tokens = await self.embedding_service.embed_query(
                question
            )

            # Step 2: Vector search
            retrieved_chunks = await self.neo4j_client.vector_search(
                query_embedding=query_embedding,
                limit=self.settings.max_chunks_retrieved,
            )

            # Step 3: Rerank and filter
            relevant_chunks = await self._rerank_chunks(
                question,
                retrieved_chunks,
                top_k=max_chunks,
            )

            # Step 4: Generate answer with Claude
            answer, input_tokens, output_tokens = await self._generate_answer(
                question, relevant_chunks
            )

            # Step 5: Extract concepts and build graph (optional)
            graph: ConceptGraph | None = None
            if include_graph and relevant_chunks:
                graph = await self._build_concept_graph(relevant_chunks)

            # Calculate metrics
            processing_time_ms = (time.time() - start_time) * 1000
            cost_cents = self._calculate_cost(
                embedding_tokens=embedding_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            logger.info(
                "rag_query_complete",
                chunks_used=len(relevant_chunks),
                processing_time_ms=processing_time_ms,
                cost_cents=cost_cents,
                embedding_tokens=embedding_tokens,
                claude_input_tokens=input_tokens,
                claude_output_tokens=output_tokens,
            )

            return QueryResponse(
                answer=answer,
                chunks=relevant_chunks,
                graph=graph,
                processing_time_ms=processing_time_ms,
                cost_cents=cost_cents,
            )

        except Exception as e:
            logger.error("rag_query_failed", error=str(e))
            raise RAGPipelineError(f"RAG pipeline failed: {str(e)}") from e

    async def _rerank_chunks(
        self,
        query: str,
        chunks: list[DocumentChunk],
        top_k: int,
    ) -> list[DocumentChunk]:
        """
        Rerank chunks using Cohere rerank API with fallback to simple scoring.

        Args:
            query: User's question
            chunks: Retrieved chunks
            top_k: Number of top chunks to keep

        Returns:
            Reranked chunks
        """
        if not chunks:
            return []

        try:
            # Prepare documents for Cohere
            documents = [chunk.content for chunk in chunks]

            # Call Cohere rerank API
            rerank_response = await self.cohere_client.rerank(
                model="rerank-v3.5",
                query=query,
                documents=documents,
                top_n=min(top_k, len(chunks)),
            )

            # Map Cohere results back to chunks with updated scores
            reranked_chunks: list[DocumentChunk] = []
            for result in rerank_response.results:
                chunk = chunks[result.index]
                # Update relevance score with Cohere's score
                chunk.metadata.relevance_score = result.relevance_score
                reranked_chunks.append(chunk)

            logger.info(
                "cohere_rerank_complete",
                input_chunks=len(chunks),
                output_chunks=len(reranked_chunks),
            )

            return reranked_chunks

        except Exception as e:
            # Fallback to simple score-based reranking
            logger.warning(
                "cohere_rerank_failed_using_fallback",
                error=str(e),
            )

            # Filter by relevance threshold
            relevant = [
                chunk
                for chunk in chunks
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
    ) -> tuple[str, int, int]:
        """
        Generate answer using Claude with anti-hallucination prompt.

        Args:
            question: User's question
            chunks: Retrieved context chunks

        Returns:
            Tuple of (generated answer, input tokens, output tokens)
        """
        if not chunks:
            return (
                "I couldn't find any relevant information in your notes to answer this question.",
                0,
                0,
            )

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
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            logger.debug(
                "answer_generated",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            return answer, input_tokens, output_tokens

        except Exception as e:
            logger.error("claude_generation_failed", error=str(e))
            raise RAGPipelineError(f"Failed to generate answer: {str(e)}") from e

    async def _build_concept_graph(
        self,
        chunks: list[DocumentChunk],
    ) -> ConceptGraph | None:
        """
        Build concept graph from concepts mentioned in retrieved chunks.

        Args:
            chunks: Retrieved document chunks

        Returns:
            Concept graph with nodes and relationships, or None if no concepts found
        """
        try:
            # Get all concepts mentioned in these chunks
            chunk_ids = [chunk.metadata.chunk_id for chunk in chunks]
            concept_names = await self.neo4j_client.get_concepts_for_chunks(chunk_ids)

            if not concept_names:
                logger.info("no_concepts_found_for_chunks")
                return None

            # Build graph by getting neighborhood around top concepts (limit to 5)
            nodes_dict: dict[str, dict] = {}
            all_edges: list[dict] = []

            for concept_name in concept_names[:5]:
                try:
                    subgraph = await self.neo4j_client.get_concept_graph(
                        concept_name, depth=1
                    )

                    # Merge nodes (avoid duplicates)
                    for node in subgraph.nodes:
                        if node.name not in nodes_dict:
                            nodes_dict[node.name] = {
                                "name": node.name,
                                "node_type": node.node_type,
                                "description": node.description,
                            }

                    # Collect edges
                    for edge in subgraph.edges:
                        all_edges.append(
                            {
                                "source": edge.source,
                                "target": edge.target,
                                "edge_type": edge.edge_type,
                                "weight": edge.weight,
                            }
                        )

                except Exception as e:
                    logger.warning(
                        "concept_subgraph_failed",
                        concept=concept_name,
                        error=str(e),
                    )
                    continue

            # Deduplicate edges
            unique_edges_set = {
                (e["source"], e["target"], e["edge_type"]) for e in all_edges
            }
            unique_edges = [
                next(e for e in all_edges if (e["source"], e["target"], e["edge_type"]) == edge_tuple)
                for edge_tuple in unique_edges_set
            ]

            from app.models.schemas import ConceptEdge, ConceptNode

            graph = ConceptGraph(
                nodes=[ConceptNode(**node_data) for node_data in nodes_dict.values()],
                edges=[ConceptEdge(**edge_data) for edge_data in unique_edges],
            )

            logger.info(
                "concept_graph_built",
                num_concepts=len(concept_names),
                num_nodes=len(graph.nodes),
                num_edges=len(graph.edges),
            )

            return graph

        except Exception as e:
            logger.warning("graph_building_failed", error=str(e))
            return None

    def _calculate_cost(
        self,
        embedding_tokens: int,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Calculate actual API cost in cents based on token usage.

        Pricing (as of November 2025):
        - OpenAI text-embedding-3-small: $0.02 per 1M tokens
        - Claude Sonnet 4.5: $3 per 1M input tokens, $15 per 1M output tokens

        Args:
            embedding_tokens: Tokens used for embeddings
            input_tokens: Claude input tokens
            output_tokens: Claude output tokens

        Returns:
            Total cost in cents
        """
        # Calculate costs in dollars
        embedding_cost = (embedding_tokens / 1_000_000) * 0.02
        claude_input_cost = (input_tokens / 1_000_000) * 3.0
        claude_output_cost = (output_tokens / 1_000_000) * 15.0

        total_cost_dollars = embedding_cost + claude_input_cost + claude_output_cost
        total_cost_cents = total_cost_dollars * 100

        return round(total_cost_cents, 4)
