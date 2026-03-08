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
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        self.redis_client: redis.Redis | None = None
        self.cache_ttl = 60 * 60 * 24 * 7

    async def connect_redis(self) -> None:
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
        if self.redis_client:
            await self.redis_client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def embed_text(self, text: str) -> tuple[list[float], int]:
        cache_key = self._get_cache_key(text)
        cached = await self._get_cached_embedding(cache_key)
        if cached:
            return cached, 0

        try:
            response = await self.client.embeddings.create(
                model=self.settings.embedding_model,
                input=text,
            )
            embedding = response.data[0].embedding
            tokens_used = response.usage.total_tokens

            await self._cache_embedding(cache_key, embedding)
            return embedding, tokens_used

        except Exception as e:
            raise EmbeddingError(f"Failed to generate embedding: {e}") from e

    async def embed_chunks(self, chunks: list[TextChunk]) -> tuple[list[EmbeddedChunk], int]:
        logger.info("embedding_chunks", num_chunks=len(chunks))

        embedded_chunks: list[EmbeddedChunk] = []
        total_tokens = 0

        for chunk in chunks:
            embedding, tokens = await self.embed_text(chunk.text)
            total_tokens += tokens
            embedded_chunks.append(
                EmbeddedChunk(
                    chunk=chunk,
                    embedding=embedding,
                    embedding_model=self.settings.embedding_model,
                )
            )

        logger.info("chunks_embedded", count=len(embedded_chunks), total_tokens=total_tokens)
        return embedded_chunks, total_tokens

    async def embed_query(self, query: str) -> tuple[list[float], int]:
        return await self.embed_text(query)

    def _get_cache_key(self, text: str) -> str:
        content = f"{self.settings.embedding_model}:{text}"
        return f"emb:{hashlib.sha256(content.encode()).hexdigest()}"

    async def _get_cached_embedding(self, cache_key: str) -> list[float] | None:
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
        if not self.redis_client:
            return
        try:
            await self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(embedding))
        except Exception as e:
            logger.warning("cache_write_failed", error=str(e))
