from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Protocol, TypeAlias, runtime_checkable


@runtime_checkable
class ClaimsAnalyzeCallable(Protocol):
    """Signature expected by ClaimsEngine extraction/verification flows."""

    def __call__(
        self,
        api_endpoint: str | None,
        input_data: Any,
        prompt: str | None,
        api_key: str | None,
        system_message: str | None,
        temp: float | None = None,
        streaming: bool = False,
        recursive_summarization: bool = False,
        chunked_summarization: bool = False,
        chunk_options: Any = None,
        model_override: str | None = None,
        response_format: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        ...


@runtime_checkable
class PromptAnalyzeCallable(Protocol):
    """Simple prompt-only callback shape used by some adjudicator tests/adapters."""

    def __call__(self, prompt: str, /) -> Any | Awaitable[Any]:
        ...


AdjudicatorAnalyzeCallable: TypeAlias = ClaimsAnalyzeCallable | PromptAnalyzeCallable


__all__ = [
    "AdjudicatorAnalyzeCallable",
    "ClaimsAnalyzeCallable",
    "PromptAnalyzeCallable",
]
