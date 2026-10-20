"""Domain exceptions. The API layer maps these to HTTP status codes without leaking internals."""
from __future__ import annotations


class AppError(Exception):
    """Base class. ``public_message`` is safe to return to API clients."""

    status_code = 500
    public_message = "Internal error."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.public_message)
        self.public_message = message or self.public_message


class PdfIngestionError(AppError):
    status_code = 422
    public_message = "The PDF could not be processed."


class PaperNotFoundError(AppError):
    status_code = 404
    public_message = "Paper not found."


class InvalidInputError(AppError):
    status_code = 400
    public_message = "Invalid input."


class VectorStoreUnavailable(AppError):
    status_code = 503
    public_message = "The vector store is unavailable."


class EmbeddingError(AppError):
    status_code = 503
    public_message = "The embedding model is unavailable."


class LLMUnavailable(AppError):
    status_code = 503
    public_message = "The language model is unavailable."

    def __init__(self, message: str | None = None, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class SummarizationUnavailable(AppError):
    status_code = 503
    public_message = "The summarization model is unavailable."
