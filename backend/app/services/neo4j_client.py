"""Neo4j client for vector search and graph operations."""

from neo4j import AsyncGraphDatabase, AsyncDriver

from app.core.config import get_settings
from app.core.exceptions import Neo4jError
from app.core.logging import get_logger
from app.models.domain import EmbeddedChunk, ExtractedConcept
from app.models.schemas import ChunkMetadata, ConceptEdge, ConceptGraph, ConceptNode, DocumentChunk

logger = get_logger(__name__)


class Neo4jClient:
    """Handles all Neo4j database operations."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Initialize Neo4j driver."""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_user, self.settings.neo4j_password),
            )
            await self.driver.verify_connectivity()
            logger.info("neo4j_connected")

            # Initialize schema and indexes
            await self._init_schema()

        except Exception as e:
            raise Neo4jError(f"Failed to connect to Neo4j: {str(e)}") from e

    async def close(self) -> None:
        """Close Neo4j driver."""
        if self.driver:
            await self.driver.close()
            logger.info("neo4j_closed")

    async def _init_schema(self) -> None:
        """Create vector index and constraints."""
        if not self.driver:
            raise Neo4jError("Driver not initialized")

        async with self.driver.session() as session:
            # Create vector index for chunks
            await session.run("""
                CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS
                FOR (c:Chunk)
                ON c.embedding
                OPTIONS {indexConfig: {
                    `vector.dimensions`: $dimensions,
                    `vector.similarity_function`: 'cosine'
                }}
            """, dimensions=self.settings.embedding_dimensions)

            # Create uniqueness constraints
            await session.run("""
                CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS
                FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE
            """)

            await session.run("""
                CREATE CONSTRAINT concept_name_unique IF NOT EXISTS
                FOR (c:Concept) REQUIRE c.name IS UNIQUE
            """)

            logger.info("neo4j_schema_initialized")

    async def store_chunks(self, embedded_chunks: list[EmbeddedChunk]) -> None:
        """
        Store embedded chunks in Neo4j.

        Args:
            embedded_chunks: List of chunks with embeddings
        """
        if not self.driver:
            raise Neo4jError("Driver not initialized")

        async with self.driver.session() as session:
            for emb_chunk in embedded_chunks:
                chunk = emb_chunk.chunk
                await session.run("""
                    MERGE (c:Chunk {chunk_id: $chunk_id})
                    SET c.text = $text,
                        c.embedding = $embedding,
                        c.source_file = $source_file,
                        c.page_num = $page_num,
                        c.course = $course,
                        c.lecture = $lecture,
                        c.embedding_model = $embedding_model
                """, {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "embedding": emb_chunk.embedding,
                    "source_file": chunk.source_file,
                    "page_num": chunk.page_num,
                    "course": chunk.metadata.get("course"),
                    "lecture": chunk.metadata.get("lecture"),
                    "embedding_model": emb_chunk.embedding_model,
                })

        logger.info("chunks_stored", count=len(embedded_chunks))

    async def vector_search(
        self,
        query_embedding: list[float],
        limit: int = 20,
    ) -> list[DocumentChunk]:
        """
        Perform vector similarity search.

        Args:
            query_embedding: Query embedding vector
            limit: Maximum number of results

        Returns:
            List of similar document chunks with scores
        """
        if not self.driver:
            raise Neo4jError("Driver not initialized")

        async with self.driver.session() as session:
            result = await session.run("""
                CALL db.index.vector.queryNodes('chunk_embeddings', $limit, $query_embedding)
                YIELD node, score
                RETURN node.chunk_id AS chunk_id,
                       node.text AS text,
                       node.course AS course,
                       node.lecture AS lecture,
                       node.page_num AS page_num,
                       score
                ORDER BY score DESC
            """, {
                "query_embedding": query_embedding,
                "limit": limit,
            })

            chunks: list[DocumentChunk] = []
            async for record in result:
                metadata = ChunkMetadata(
                    chunk_id=record["chunk_id"],
                    course=record["course"],
                    lecture=record["lecture"],
                    page_num=record["page_num"],
                    relevance_score=record["score"],
                )
                chunk = DocumentChunk(
                    content=record["text"],
                    metadata=metadata,
                )
                chunks.append(chunk)

            logger.info("vector_search_complete", results=len(chunks))
            return chunks

    async def store_concepts(
        self,
        concepts: list[ExtractedConcept],
        chunk_id: str,
    ) -> None:
        """
        Store extracted concepts and link to chunk.

        Args:
            concepts: List of extracted concepts
            chunk_id: Source chunk ID
        """
        if not self.driver:
            raise Neo4jError("Driver not initialized")

        async with self.driver.session() as session:
            for concept in concepts:
                # Create concept node
                await session.run("""
                    MERGE (c:Concept {name: $name})
                    SET c.concept_type = $concept_type
                """, {
                    "name": concept.name,
                    "concept_type": concept.concept_type,
                })

                # Link concept to chunk
                await session.run("""
                    MATCH (chunk:Chunk {chunk_id: $chunk_id})
                    MATCH (concept:Concept {name: $concept_name})
                    MERGE (concept)-[:MENTIONED_IN]->(chunk)
                """, {
                    "chunk_id": chunk_id,
                    "concept_name": concept.name,
                })

        logger.info("concepts_stored", count=len(concepts), chunk_id=chunk_id)

    async def create_concept_relations(self, concept_pairs: list[tuple[str, str]]) -> None:
        """
        Create RELATES_TO edges between concepts that co-occur.

        Args:
            concept_pairs: List of (concept1, concept2) tuples
        """
        if not self.driver:
            raise Neo4jError("Driver not initialized")

        async with self.driver.session() as session:
            for concept1, concept2 in concept_pairs:
                await session.run("""
                    MATCH (c1:Concept {name: $concept1})
                    MATCH (c2:Concept {name: $concept2})
                    MERGE (c1)-[r:RELATES_TO]-(c2)
                    ON CREATE SET r.weight = 1
                    ON MATCH SET r.weight = r.weight + 1
                """, {
                    "concept1": concept1,
                    "concept2": concept2,
                })

    async def get_concept_graph(self, concept_name: str, depth: int = 2) -> ConceptGraph:
        """
        Get neighborhood graph around a concept.

        Args:
            concept_name: Central concept
            depth: How many hops to traverse

        Returns:
            Knowledge graph structure
        """
        if not self.driver:
            raise Neo4jError("Driver not initialized")

        async with self.driver.session() as session:
            result = await session.run(f"""
                MATCH path = (c:Concept {{name: $concept_name}})-[:RELATES_TO*1..{depth}]-(related:Concept)
                RETURN c, related, relationships(path) as rels
                LIMIT 50
            """, {
                "concept_name": concept_name,
            })

            nodes_dict: dict[str, ConceptNode] = {}
            edges: list[ConceptEdge] = []

            async for record in result:
                # Add nodes
                for node in [record["c"], record["related"]]:
                    if node["name"] not in nodes_dict:
                        nodes_dict[node["name"]] = ConceptNode(
                            name=node["name"],
                            node_type="concept",
                        )

                # Add edges
                for rel in record["rels"]:
                    edge = ConceptEdge(
                        source=rel.start_node["name"],
                        target=rel.end_node["name"],
                        edge_type="RELATES_TO",
                        weight=rel.get("weight", 1.0),
                    )
                    edges.append(edge)

            return ConceptGraph(
                nodes=list(nodes_dict.values()),
                edges=edges,
            )

    async def health_check(self) -> bool:
        """Check if Neo4j is connected and responsive."""
        if not self.driver:
            return False

        try:
            await self.driver.verify_connectivity()
            return True
        except Exception:
            return False
