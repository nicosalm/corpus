from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API keys
    anthropic_api_key: str
    openai_api_key: str
    cohere_api_key: str
    fish_audio_api_key: str | None = None

    # Infrastructure
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str
    redis_url: str = "redis://localhost:6379"

    # Application
    environment: str = "development"
    log_level: str = "INFO"

    # Models
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    claude_model: str = "claude-sonnet-4-5-20250929"

    # Chunking
    chunk_size: int = 800
    chunk_overlap: int = 100

    # RAG
    max_chunks_retrieved: int = 20
    rerank_top_k: int = 5
    relevance_threshold: float = 0.5

    # Caching
    response_cache_ttl: int = 60 * 60 * 24  # 1 day


@lru_cache
def get_settings() -> Settings:
    return Settings()
