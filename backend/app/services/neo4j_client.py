from neo4j import AsyncDriver, AsyncGraphDatabase

from app.core.config import get_settings
from app.core.exceptions import Neo4jError
from app.core.logging import get_logger
from app.models.domain import EmbeddedChunk, ExtractedConcept
from app.models.schemas import ChunkMetadata, ConceptEdge, ConceptGraph, ConceptNode, DocumentChunk

logger = get_logger(__name__)

# Pre-built Cypher queries keyed by depth to avoid f-string interpolation of user input.
_CONCEPT_GRAPH_QUERIES = {
    depth: f"""
        MATCH path = (c:Concept {{name: $concept_name}})-[:RELATES_TO*1..{depth}]-(related:Concept)
        RETURN c, related, relationships(path) as rels
        LIMIT 50
    """
    for depth in range(1, 5)
}


class Neo4jClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.driver: AsyncDriver | None = None

    async def connect(self) -> None:
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_user, self.settings.neo4j_password),
            )
            await self.driver.verify_connectivity()
            logger.info("neo4j_connected")
            await self._init_schema()
        except Exception as e:
            raise Neo4jError(f"Failed to connect to Neo4j: {e}") from e

    async def close(self) -> None:
        if self.driver:
            await self.driver.close()
            logger.info("neo4j_closed")

    async def _init_schema(self) -> None:
        if not self.driver:
            raise Neo4jError("Driver not initialized")

        async with self.driver.session() as session:
            await session.run("""
                CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS
                FOR (c:Chunk)
                ON c.embedding
                OPTIONS {indexConfig: {
                    `vector.dimensions`: $dimensions,
                    `vector.similarity_function`: 'cosine'
                }}
            """, dimensions=self.settings.embedding_dimensions)

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
        if not self.driver:
            raise Neo4jError("Driver not initialized")
        if not embedded_chunks:
            return

        rows = [
            {
                "chunk_id": ec.chunk.chunk_id,
                "text": ec.chunk.text,
                "embedding": ec.embedding,
                "source_file": ec.chunk.source_file,
                "page_num": ec.chunk.page_num,
                "course": ec.chunk.metadata.get("course"),
                "lecture": ec.chunk.metadata.get("lecture"),
                "embedding_model": ec.embedding_model,
            }
            for ec in embedded_chunks
        ]

        async with self.driver.session() as session:
            await session.run("""
                UNWIND $rows AS row
                MERGE (c:Chunk {chunk_id: row.chunk_id})
                SET c.text = row.text,
                    c.embedding = row.embedding,
                    c.source_file = row.source_file,
                    c.page_num = row.page_num,
                    c.course = row.course,
                    c.lecture = row.lecture,
                    c.embedding_model = row.embedding_model
            """, {"rows": rows})

        logger.info("chunks_stored", count=len(embedded_chunks))

    async def vector_search(
        self,
        query_embedding: list[float],
        limit: int = 20,
    ) -> list[DocumentChunk]:
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
                chunks.append(DocumentChunk(
                    content=record["text"],
                    metadata=ChunkMetadata(
                        chunk_id=record["chunk_id"],
                        course=record["course"],
                        lecture=record["lecture"],
                        page_num=record["page_num"],
                        relevance_score=record["score"],
                    ),
                ))

            logger.info("vector_search_complete", results=len(chunks))
            return chunks

    async def store_concepts(
        self,
        concepts: list[ExtractedConcept],
        chunk_id: str,
    ) -> None:
        if not self.driver:
            raise Neo4jError("Driver not initialized")
        if not concepts:
            return

        rows = [{"name": c.name, "concept_type": c.concept_type} for c in concepts]

        async with self.driver.session() as session:
            await session.run("""
                UNWIND $rows AS row
                MERGE (c:Concept {name: row.name})
                SET c.concept_type = row.concept_type
            """, {"rows": rows})

            await session.run("""
                MATCH (chunk:Chunk {chunk_id: $chunk_id})
                UNWIND $names AS name
                MATCH (concept:Concept {name: name})
                MERGE (concept)-[:MENTIONED_IN]->(chunk)
            """, {
                "chunk_id": chunk_id,
                "names": [c.name for c in concepts],
            })

        logger.info("concepts_stored", count=len(concepts), chunk_id=chunk_id)

    async def create_concept_relations(self, concept_pairs: list[tuple[str, str]]) -> None:
        if not self.driver:
            raise Neo4jError("Driver not initialized")
        if not concept_pairs:
            return

        rows = [{"c1": c1, "c2": c2} for c1, c2 in concept_pairs]

        async with self.driver.session() as session:
            await session.run("""
                UNWIND $rows AS row
                MATCH (c1:Concept {name: row.c1})
                MATCH (c2:Concept {name: row.c2})
                MERGE (c1)-[r:RELATES_TO]-(c2)
                ON CREATE SET r.weight = 1
                ON MATCH SET r.weight = r.weight + 1
            """, {"rows": rows})

    async def get_concepts_for_chunks(self, chunk_ids: list[str]) -> list[str]:
        if not self.driver:
            raise Neo4jError("Driver not initialized")

        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (c:Concept)-[:MENTIONED_IN]->(chunk:Chunk)
                WHERE chunk.chunk_id IN $chunk_ids
                RETURN DISTINCT c.name AS name
                ORDER BY c.name
            """, {"chunk_ids": chunk_ids})

            return [record["name"] async for record in result]

    async def get_concept_graph(self, concept_name: str, depth: int = 2) -> ConceptGraph:
        if not self.driver:
            raise Neo4jError("Driver not initialized")
        if depth not in _CONCEPT_GRAPH_QUERIES:
            raise ValueError(f"depth must be 1-4, got {depth}")

        async with self.driver.session() as session:
            result = await session.run(
                _CONCEPT_GRAPH_QUERIES[depth],
                {"concept_name": concept_name},
            )

            nodes_dict: dict[str, ConceptNode] = {}
            edges: list[ConceptEdge] = []

            async for record in result:
                for node in [record["c"], record["related"]]:
                    if node["name"] not in nodes_dict:
                        nodes_dict[node["name"]] = ConceptNode(
                            name=node["name"],
                            node_type="concept",
                        )

                for rel in record["rels"]:
                    edges.append(ConceptEdge(
                        source=rel.start_node["name"],
                        target=rel.end_node["name"],
                        edge_type="RELATES_TO",
                        weight=rel.get("weight", 1.0),
                    ))

            return ConceptGraph(nodes=list(nodes_dict.values()), edges=edges)

    async def health_check(self) -> bool:
        if not self.driver:
            return False
        try:
            await self.driver.verify_connectivity()
            return True
        except Exception:
            return False
