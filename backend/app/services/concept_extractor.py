import asyncio
import json

from anthropic import AsyncAnthropic

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.domain import ExtractedConcept, TextChunk

logger = get_logger(__name__)

_VALID_CONCEPT_TYPES = {"algorithm", "topic", "theory", "technique", "term", "person"}

_EXTRACTION_PROMPT = """\
You are a concept extraction AI for academic notes. \
Extract key concepts from the following text.

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
{text}

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


class ConceptExtractor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

    async def extract_concepts(self, chunk: TextChunk) -> list[ExtractedConcept]:
        try:
            response = await self.client.messages.create(
                model=self.settings.claude_model,
                max_tokens=2048,
                messages=[{"role": "user", "content": _EXTRACTION_PROMPT.format(text=chunk.text)}],
            )

            response_text = response.content[0].text.strip()

            # Strip code fences if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            concepts_data = json.loads(response_text)
            concepts: list[ExtractedConcept] = []

            for item in concepts_data:
                if item.get("concept_type") not in _VALID_CONCEPT_TYPES:
                    logger.warning(
                        "invalid_concept_type",
                        type=item.get("concept_type"),
                        name=item.get("name"),
                    )
                    continue

                confidence = item.get("confidence", 0.5)
                if not (0.0 <= confidence <= 1.0):
                    confidence = 0.5

                concepts.append(ExtractedConcept(
                    name=item["name"],
                    concept_type=item["concept_type"],
                    context=item.get("context", ""),
                    confidence=confidence,
                ))

            logger.info("concepts_extracted", chunk_id=chunk.chunk_id, num_concepts=len(concepts))
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
            logger.error("concept_extraction_failed", chunk_id=chunk.chunk_id, error=str(e))
            return []

    async def extract_batch(
        self,
        chunks: list[TextChunk],
        max_concurrency: int = 5,
    ) -> dict[str, list[ExtractedConcept]]:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _extract(chunk: TextChunk) -> tuple[str, list[ExtractedConcept]]:
            async with semaphore:
                return chunk.chunk_id, await self.extract_concepts(chunk)

        results_list = await asyncio.gather(*[_extract(c) for c in chunks])

        logger.info(
            "batch_extraction_complete",
            total_chunks=len(chunks),
            total_concepts=sum(len(concepts) for _, concepts in results_list),
        )
        return dict(results_list)
