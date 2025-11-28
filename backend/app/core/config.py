"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API Keys
    anthropic_api_key: str = Field(..., description="Anthropic API key for Claude")
    openai_api_key: str = Field(..., description="OpenAI API key for embeddings")
    fish_audio_api_key: str = Field(..., description="Fish Audio API key for TTS")

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687", description="Neo4j connection URI")
    neo4j_user: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: str = Field(..., description="Neo4j password")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")

    # Application
    environment: str = Field(default="development", description="Environment name")
    log_level: str = Field(default="INFO", description="Logging level")

    # Embedding Configuration
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model to use",
    )
    embedding_dimensions: int = Field(
        default=1536,
        description="Embedding vector dimensions",
    )

    # Claude Configuration
    claude_model: str = Field(
        default="claude-sonnet-4-5-20250929",
        description="Anthropic Claude model to use (sonnet-4-5, opus-4-5, or haiku-4-5)",
    )

    # Chunking Configuration
    chunk_size: int = Field(default=800, description="Target chunk size in tokens")
    chunk_overlap: int = Field(default=100, description="Overlap between chunks in tokens")

    # RAG Configuration
    max_chunks_retrieved: int = Field(
        default=20,
        description="Maximum chunks to retrieve from vector search",
    )
    rerank_top_k: int = Field(default=5, description="Top K chunks after reranking")
    relevance_threshold: float = Field(
        default=0.5,
        description="Minimum relevance score for chunks",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
