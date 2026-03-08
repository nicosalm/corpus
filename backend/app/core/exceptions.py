class CorpusError(Exception):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class PDFProcessingError(CorpusError):
    pass


class ChunkingError(CorpusError):
    pass


class EmbeddingError(CorpusError):
    pass


class Neo4jError(CorpusError):
    pass


class RAGPipelineError(CorpusError):
    pass


class ValidationError(CorpusError):
    pass
