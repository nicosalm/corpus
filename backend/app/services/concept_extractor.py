"""Concept extraction service using Claude."""

import json
from anthropic import AsyncAnthropic

from app.core.config import get_settings
from app.core.exceptions import RAGPipelineError
from app.core.logging import get_logger
from app.models.domain import ExtractedConcept, TextChunk

logger = get_logger(__name__)


class ConceptExtractor:
    """Extract semantic concepts from text chunks using Claude."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

    async def extract_concepts(self, chunk: TextChunk) -> list[ExtractedConcept]:
        """
        Extract key concepts from a text chunk.

        Identifies:
        - Algorithms (e.g., K-Means, Dijkstra's Algorithm)
        - Topics (e.g., Machine Learning, Graph Theory)
        - Theories (e.g., Big-O Notation, Bayes' Theorem)
        - Techniques (e.g., Dynamic Programming, Backtracking)
        - Terms (e.g., Eigenvalue, Gradient Descent)
        - People (e.g., Turing, Dijkstra)

        Args:
            chunk: Text chunk to analyze

        Returns:
            List of extracted concepts with metadata
        """
        prompt = f"""You are a concept extraction AI for academic notes. Extract key concepts from the following text.

For each concept, provide:
1. **name**: The concept name (2-5 words, title case)
2. **concept_type**: One of: "algorithm", "topic", "theory", "technique", "term", "person"
3. **context**: A brief phrase showing how it's used (10-20 words)
4. **confidence**: Your confidence in this extraction (0.0-1.0)

RULES:
- Extract 3-10 most important concepts
- Focus on concrete, specific concepts (not vague terms)
- Use canonical names (e.g., "K-Means Clustering" not "k means")
- Only extract concepts actually mentioned in the text
- High confidence (>0.8) for explicitly defined concepts
- Medium confidence (0.5-0.8) for implied/referenced concepts
- Skip generic words like "data", "example", "chapter"

TEXT TO ANALYZE:
{chunk.text}

Respond with a JSON array of concepts:
```json
[
  {{
    "name": "Concept Name",
    "concept_type": "algorithm",
    "context": "brief context from text",
    "confidence": 0.9
  }}
]
```

JSON array of concepts:"""

        try:
            response = await self.client.messages.create(
                model=self.settings.claude_model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract JSON from response
            response_text = response.content[0].text.strip()

            # Handle markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            # Parse JSON
            concepts_data = json.loads(response_text)

            # Validate and convert to ExtractedConcept objects
            concepts: list[ExtractedConcept] = []
            valid_types = {"algorithm", "topic", "theory", "technique", "term", "person"}

            for concept_dict in concepts_data:
                # Validate concept_type
                if concept_dict.get("concept_type") not in valid_types:
                    logger.warning(
                        "invalid_concept_type",
                        type=concept_dict.get("concept_type"),
                        name=concept_dict.get("name"),
                    )
                    continue

                # Validate confidence range
                confidence = concept_dict.get("confidence", 0.5)
                if not (0.0 <= confidence <= 1.0):
                    confidence = 0.5

                concepts.append(
                    ExtractedConcept(
                        name=concept_dict["name"],
                        concept_type=concept_dict["concept_type"],
                        context=concept_dict.get("context", ""),
                        confidence=confidence,
                    )
                )

            logger.info(
                "concepts_extracted",
                chunk_id=chunk.chunk_id,
                num_concepts=len(concepts),
            )

            return concepts

        except json.JSONDecodeError as e:
            logger.error(
                "concept_extraction_json_parse_failed",
                chunk_id=chunk.chunk_id,
                error=str(e),
                response=response_text[:200] if "response_text" in locals() else "N/A",
            )
            return []

        except Exception as e:
            logger.error(
                "concept_extraction_failed",
                chunk_id=chunk.chunk_id,
                error=str(e),
            )
            return []

    async def extract_batch(
        self,
        chunks: list[TextChunk],
        batch_size: int = 5,
    ) -> dict[str, list[ExtractedConcept]]:
        """
        Extract concepts from multiple chunks in batches.

        Args:
            chunks: List of text chunks
            batch_size: Number of chunks to process at once (not implemented yet)

        Returns:
            Dict mapping chunk_id to list of concepts
        """
        results: dict[str, list[ExtractedConcept]] = {}

        for chunk in chunks:
            concepts = await self.extract_concepts(chunk)
            results[chunk.chunk_id] = concepts

        logger.info(
            "batch_extraction_complete",
            total_chunks=len(chunks),
            total_concepts=sum(len(concepts) for concepts in results.values()),
        )

        return results
