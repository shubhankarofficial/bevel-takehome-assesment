"""
API error response shape.

Use for 4xx/5xx responses so clients get a consistent structure.
Common errors are available as class methods so message and code stay in one place.
"""

from typing import Optional

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Structured error body. Use for validation and server errors."""

    message: str
    code: Optional[str] = None

    @classmethod
    def query_required(cls) -> "ErrorResponse":
        """Search endpoint: query parameter is missing or empty."""
        return cls(message="query is required", code="QUERY_REQUIRED")

    @classmethod
    def invalid_size(cls) -> "ErrorResponse":
        """Search endpoint: size must be between 1 and 100."""
        return cls(message="size must be between 1 and 100", code="INVALID_SIZE")

    @classmethod
    def search_unavailable(cls) -> "ErrorResponse":
        """Search temporarily unavailable (e.g. Elasticsearch down or timeout)."""
        return cls(message="Search is temporarily unavailable", code="SEARCH_UNAVAILABLE")

    @classmethod
    def internal_error(cls, message: str = "An unexpected error occurred") -> "ErrorResponse":
        """Generic server error. Override message for logging context if needed."""
        return cls(message=message, code="INTERNAL_ERROR")
