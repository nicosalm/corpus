# Neo4j Query Cheat Sheet - Corpus Knowledge Graph

Quick reference for exploring the Corpus knowledge graph in Neo4j Browser (`http://localhost:7474`)

---

## Basic Exploration

### Count Everything
```cypher
// Total concepts
MATCH (c:Concept) RETURN count(c) as total_concepts

// Total chunks
MATCH (ch:Chunk) RETURN count(ch) as total_chunks

// Total relationships
MATCH ()-[r:RELATES_TO]-() RETURN count(r)/2 as total_relations

// Total MENTIONED_IN links
MATCH ()-[r:MENTIONED_IN]->() RETURN count(r) as mentions
```

### Sample Data
```cypher
// Random 25 concepts
MATCH (c:Concept) RETURN c.name, c.concept_type LIMIT 25

// Concepts by type
MATCH (c:Concept)
WHERE c.concept_type = "algorithm"
RETURN c.name
ORDER BY c.name
```

---

## Relationship Analysis

### Most Connected Concepts
```cypher
MATCH (c:Concept)-[r:RELATES_TO]-()
RETURN c.name, c.concept_type, count(r) as connections
ORDER BY connections DESC
LIMIT 20
```

### Strongest Relationships
```cypher
MATCH (c1:Concept)-[r:RELATES_TO]-(c2:Concept)
RETURN c1.name, c2.name, r.weight
ORDER BY r.weight DESC
LIMIT 30
```

### Relationship Weight Distribution
```cypher
MATCH ()-[r:RELATES_TO]-()
RETURN r.weight, count(*)/2 as count
ORDER BY r.weight DESC
```

---

## Graph Visualization

### Concept Neighborhood (1-hop)
```cypher
MATCH (c:Concept {name: "Singular Value Decomposition"})-[r:RELATES_TO]-(related:Concept)
RETURN c, r, related
LIMIT 50
```

### Concept Neighborhood (2-hops)
```cypher
MATCH path = (c:Concept {name: "K-Means Algorithm"})-[:RELATES_TO*1..2]-(related:Concept)
RETURN path
LIMIT 100
```

### Subgraph by Type
```cypher
// All algorithms and their connections
MATCH (c1:Concept)-[r:RELATES_TO]-(c2:Concept)
WHERE c1.concept_type = "algorithm" OR c2.concept_type = "algorithm"
RETURN c1, r, c2
LIMIT 100
```

---

## Concept-Chunk Relationships

### Find Chunks Mentioning a Concept
```cypher
MATCH (c:Concept {name: "Principal Component Analysis"})-[:MENTIONED_IN]->(chunk:Chunk)
RETURN chunk.text, chunk.page_num
LIMIT 10
```

### Concepts Per Chunk
```cypher
MATCH (chunk:Chunk)<-[:MENTIONED_IN]-(c:Concept)
WITH chunk.chunk_id as chunk_id, collect(c.name) as concepts
RETURN chunk_id, size(concepts) as concept_count, concepts
ORDER BY concept_count DESC
LIMIT 20
```

### Co-occurring Concepts
```cypher
// Find concepts that appear together in same chunks
MATCH (c1:Concept)-[:MENTIONED_IN]->(chunk:Chunk)<-[:MENTIONED_IN]-(c2:Concept)
WHERE c1.name < c2.name  // Avoid duplicates
RETURN c1.name, c2.name, count(chunk) as co_occurrences
ORDER BY co_occurrences DESC
LIMIT 30
```

---

## Advanced Queries

### Find Concept Clusters
```cypher
// Concepts with many shared neighbors
MATCH (c1:Concept)-[:RELATES_TO]-(shared:Concept)-[:RELATES_TO]-(c2:Concept)
WHERE c1.name < c2.name AND NOT (c1)-[:RELATES_TO]-(c2)
RETURN c1.name, c2.name, count(shared) as shared_neighbors
ORDER BY shared_neighbors DESC
LIMIT 20
```

### Search Concepts by Name Pattern
```cypher
MATCH (c:Concept)
WHERE c.name CONTAINS "Matrix"
RETURN c.name, c.concept_type
ORDER BY c.name
```

### Concept Path Between Two Topics
```cypher
MATCH path = shortestPath(
  (c1:Concept {name: "K-Means Algorithm"})-[:RELATES_TO*..5]-(c2:Concept {name: "Principal Component Analysis"})
)
RETURN path
```

### Bridge Concepts (connect different clusters)
```cypher
MATCH (c:Concept)-[r:RELATES_TO]-()
WITH c, count(r) as connections
WHERE connections > 10
MATCH (c)-[r2:RELATES_TO]-(neighbor:Concept)
WITH c, neighbor, count(r2) as shared
ORDER BY shared DESC
RETURN c.name, collect(neighbor.name)[0..5] as top_neighbors, connections
LIMIT 20
```

---

## Statistics & Analysis

### Concepts by Type Distribution
```cypher
MATCH (c:Concept)
RETURN c.concept_type as type, count(*) as count
ORDER BY count DESC
```

### Average Connections Per Concept
```cypher
MATCH (c:Concept)
OPTIONAL MATCH (c)-[r:RELATES_TO]-()
WITH c, count(r) as connections
RETURN
  avg(connections) as avg_connections,
  min(connections) as min_connections,
  max(connections) as max_connections,
  stdev(connections) as std_dev
```

### Isolated Concepts (no relationships)
```cypher
MATCH (c:Concept)
WHERE NOT (c)-[:RELATES_TO]-()
RETURN c.name, c.concept_type
```

---

## Debugging & Cleanup

### Delete All Relationships (keep nodes)
```cypher
MATCH ()-[r:RELATES_TO]-() DELETE r
```

### Delete Everything
```cypher
MATCH (n) DETACH DELETE n
```

### Check for Duplicates
```cypher
MATCH (c:Concept)
WITH c.name as name, collect(c) as concepts
WHERE size(concepts) > 1
RETURN name, size(concepts) as duplicates
```

### Find Orphaned Chunks (no concepts)
```cypher
MATCH (chunk:Chunk)
WHERE NOT (:Concept)-[:MENTIONED_IN]->(chunk)
RETURN chunk.chunk_id, chunk.text[0..100] as preview
LIMIT 10
```

---

## Useful Filters

### High-Confidence Relationships Only
```cypher
// Concepts that co-occur 3+ times
MATCH (c1:Concept)-[r:RELATES_TO]-(c2:Concept)
WHERE r.weight >= 3
RETURN c1.name, c2.name, r.weight
ORDER BY r.weight DESC
```

### Filter by Course/Source
```cypher
MATCH (chunk:Chunk)<-[:MENTIONED_IN]-(c:Concept)
WHERE chunk.course = "CS532"
RETURN DISTINCT c.name, c.concept_type
ORDER BY c.name
```

---

## Export Queries

### Export Concept List (CSV)
```cypher
MATCH (c:Concept)
RETURN c.name as name, c.concept_type as type
ORDER BY c.name
// Click "Download CSV" in Neo4j Browser
```

### Export Graph Structure
```cypher
MATCH (c1:Concept)-[r:RELATES_TO]-(c2:Concept)
WHERE c1.name < c2.name
RETURN c1.name as source, c2.name as target, r.weight as weight
ORDER BY weight DESC
// Click "Download CSV" for D3.js/Gephi import
```

---

## Tips

1. **Performance:** Add `LIMIT` to prevent browser freezing on large graphs
2. **Visualization:** Use `RETURN path` instead of `RETURN c1, r, c2` for better graph layout
3. **Debugging:** Check `docker-compose logs backend` for concept extraction errors
4. **Styling:** In Neo4j Browser, click a node → Style → Change colors/sizes by type

---

## Common Troubleshooting

**Q: "Relationship type RELATES_TO not found"**
A: Concept extraction hasn't created relationships yet. Wait for ingestion to complete.

**Q: "All weights are 1"**
A: Using old file-level relationship logic. Use chunk-level logic (fixed in Phase 2).

**Q: "Concept not found"**
A: Use full canonical names ("Principal Component Analysis" not "PCA")

**Q: "Graph is too dense"**
A: Filter by `WHERE r.weight >= 3` to show only strong relationships
