"""Embedding generation service with caching."""

import hashlib
import json

import redis.asyncio as redis
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.exceptions import EmbeddingError
from app.core.logging import get_logger
from app.models.domain import EmbeddedChunk, TextChunk

logger = get_logger(__name__)


class EmbeddingService:
    """Handles embedding generation with Redis caching."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        self.redis_client: redis.Redis | None = None
        self.cache_ttl = 60 * 60 * 24 * 7  # 7 days

    async def connect_redis(self) -> None:
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                self.settings.redis_url,
                encoding="utf-8",
                decode_responses=False,
            )
            await self.redis_client.ping()
            logger.info("redis_connected")
        except Exception as e:
            logger.warning("redis_connection_failed", error=str(e))
            self.redis_client = None

    async def close_redis(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def embed_text(self, text: str) -> tuple[list[float], int]:
        """
        Generate embedding for text with caching and retry.

        Args:
            text: Text to embed

        Returns:
            Tuple of (embedding vector, token count)

        Raises:
            EmbeddingError: If embedding generation fails
        """
        # Check cache first
        cache_key = self._get_cache_key(text)
        cached = await self._get_cached_embedding(cache_key)
        if cached:
            logger.debug("embedding_cache_hit", cache_key=cache_key)
            # Cached embeddings don't incur token costs
            return cached, 0

        # Generate embedding
        try:
            logger.debug("generating_embedding", text_length=len(text))

            response = await self.client.embeddings.create(
                model=self.settings.embedding_model,
                input=text,
            )

            embedding = response.data[0].embedding
            tokens_used = response.usage.total_tokens

            # Cache the result
            await self._cache_embedding(cache_key, embedding)

            logger.debug(
                "embedding_generated",
                dimensions=len(embedding),
                tokens=tokens_used,
            )
            return embedding, tokens_used

        except Exception as e:
            raise EmbeddingError(f"Failed to generate embedding: {str(e)}") from e

    async def embed_chunks(self, chunks: list[TextChunk]) -> tuple[list[EmbeddedChunk], int]:
        """
        Generate embeddings for multiple chunks.

        Args:
            chunks: List of text chunks

        Returns:
            Tuple of (list of embedded chunks, total tokens used)
        """
        logger.info("embedding_chunks", num_chunks=len(chunks))

        embedded_chunks: list[EmbeddedChunk] = []
        total_tokens = 0

        for chunk in chunks:
            embedding, tokens = await self.embed_text(chunk.text)
            total_tokens += tokens
            embedded_chunk = EmbeddedChunk(
                chunk=chunk,
                embedding=embedding,
                embedding_model=self.settings.embedding_model,
            )
            embedded_chunks.append(embedded_chunk)

        logger.info(
            "chunks_embedded",
            count=len(embedded_chunks),
            total_tokens=total_tokens,
        )
        return embedded_chunks, total_tokens

    async def embed_query(self, query: str) -> tuple[list[float], int]:
        """
        Generate embedding for a search query.

        Args:
            query: Search query text

        Returns:
            Tuple of (query embedding vector, tokens used)
        """
        return await self.embed_text(query)

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text and model."""
        content = f"{self.settings.embedding_model}:{text}"
        return f"emb:{hashlib.sha256(content.encode()).hexdigest()}"

    async def _get_cached_embedding(self, cache_key: str) -> list[float] | None:
        """Retrieve embedding from cache."""
        if not self.redis_client:
            return None

        try:
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning("cache_read_failed", error=str(e))

        return None

    async def _cache_embedding(self, cache_key: str, embedding: list[float]) -> None:
        """Store embedding in cache."""
        if not self.redis_client:
            return

        try:
            await self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(embedding),
            )
        except Exception as e:
            logger.warning("cache_write_failed", error=str(e))
