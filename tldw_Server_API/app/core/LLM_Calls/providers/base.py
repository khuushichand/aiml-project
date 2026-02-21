from __future__ import annotations

"""
Base interfaces and helpers for LLM provider adapters.

Adapters implement a unified ChatProvider interface and are responsible for:
- Auth + base URL resolution
- Request payload shaping (OpenAI-like input)
- Streaming normalization via shared SSE helpers
- Error mapping to Chat*Error types

Adapters should return OpenAI-compatible chat completion JSON for non-streaming
and yield OpenAI-compatible SSE lines for streaming.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterable
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Chat.Chat_Deps import (
    ChatAPIError,
    ChatAuthenticationError,
    ChatBadRequestError,
    ChatProviderError,
    ChatRateLimitError,
)


class ChatProvider(ABC):
    """Abstract base for LLM chat providers."""

    name: str = "provider"

    @abstractmethod
    def capabilities(self) -> dict[str, Any]:
        """Return provider capability flags and hints.

        Example keys:
        - supports_streaming: bool
        - supports_tools: bool
        - json_mode: bool
        - default_timeout_seconds: int
        - max_output_tokens_default: Optional[int]
        """

    @abstractmethod
    def chat(self, request: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        """Non-streaming chat completion (OpenAI-compatible response)."""

    @abstractmethod
    def stream(self, request: dict[str, Any], *, timeout: float | None = None) -> Iterable[str]:
        """Streaming chat completion.

        Yields OpenAI-compatible SSE lines. Callers are responsible for emitting a
        final [DONE] using sse.finalize_stream() to avoid duplicates.
        """

    async def achat(self, request: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        """Async variant; adapters may override for native async paths.

        Default raises NotImplementedError to avoid silent sync-in-async fallbacks.
        """
        raise NotImplementedError("Async chat not implemented for this provider")

    async def astream(self, request: dict[str, Any], *, timeout: float | None = None) -> AsyncIterator[str]:
        """Async streaming variant; adapters may override for native async paths."""
        raise NotImplementedError("Async stream not implemented for this provider")

    def normalize_error(self, exc: Exception) -> ChatAPIError:
        """Map arbitrary exceptions to project Chat*Error classes.

        Adapters may override for provider-specific error shapes. This default
        provides a conservative mapping for common HTTP exceptions if available,
        falling back to ChatProviderError.
        """
        from tldw_Server_API.app.core.LLM_Calls.error_utils import (
            get_http_error_text,
            get_http_status_from_exception,
            is_http_status_error,
        )

        if is_http_status_error(exc):
            status = get_http_status_from_exception(exc)
            detail = get_http_error_text(exc)
            if status in (400, 404, 422):
                return ChatBadRequestError(provider=self.name, message=str(detail))
            if status in (401, 403):
                return ChatAuthenticationError(provider=self.name, message=str(detail))
            if status == 429:
                return ChatRateLimitError(provider=self.name, message=str(detail))
            if status and 500 <= status < 600:
                return ChatProviderError(provider=self.name, message=str(detail), status_code=status)
            return ChatAPIError(provider=self.name, message=str(detail), status_code=status or 500)

        # Fallback
        logger.debug(f"{self.name}: normalizing generic error: {exc}")
        return ChatProviderError(provider=self.name, message=str(exc))


def apply_tool_choice(payload: dict[str, Any], tools: list | None, tool_choice: Any | None) -> None:
    """Safely set tool_choice only when supported.

    - Always honor explicit "none" to disable tools.
    - Apply tool_choice only if provided and tools list is present.
    """
    try:
        if tool_choice == "none":
            payload["tool_choice"] = "none"
        elif tool_choice is not None and tools:
            payload["tool_choice"] = tool_choice
    except Exception as payload_error:
        # Never fail due to helper
        logger.debug("Provider payload helper failed while attaching tool metadata", exc_info=payload_error)


class EmbeddingsProvider(ABC):
    """Abstract base for embeddings providers.

    Implementations should return OpenAI-compatible embeddings responses or
    a plain list/array of floats when used as a library.
    """

    name: str = "embeddings_provider"

    @abstractmethod
    def capabilities(self) -> dict[str, Any]:
        """Return provider capability flags and hints.

        Example keys:
        - dimensions_default: Optional[int]
        - max_batch_size: Optional[int]
        - default_timeout_seconds: int
        """

    @abstractmethod
    def embed(self, request: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        """Create embeddings for given input(s).

        Request shape should accept keys similar to OpenAI's API:
        - input: Union[str, List[str]]
        - model: str
        - api_key: Optional[str]
        - user: Optional[str]
        - encoding_format: Optional[str]
        """
