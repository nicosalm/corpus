"""Custom exceptions for the application."""


class CorpusException(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class PDFProcessingError(CorpusException):
    """Raised when PDF processing fails."""

    pass


class EmbeddingError(CorpusException):
    """Raised when embedding generation fails."""

    pass


class Neo4jError(CorpusException):
    """Raised when Neo4j operations fail."""

    pass


class RAGPipelineError(CorpusException):
    """Raised when RAG pipeline execution fails."""

    pass


class ChunkingError(CorpusException):
    """Raised when text chunking fails."""

    pass


class ValidationError(CorpusException):
    """Raised when input validation fails."""

    pass
