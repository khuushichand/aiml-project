from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .chat_request_schemas import ChatCompletionMessageParam


class LlamaCppInferenceRequest(BaseModel):
    """OpenAI-style chat completion payload with permissive extras.

    Use extra='allow' so llama.cpp-specific fields can pass through without validation loss.
    """
    model_config = ConfigDict(extra='allow')

    model: str | None = Field(default=None, description="Model identifier; may be ignored by active server")
    messages: list[ChatCompletionMessageParam] | None = Field(default=None, description="Chat messages")
    stream: bool | None = Field(default=None)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, ge=1)
    stop: str | list[str] | None = Field(default=None)
    user: str | None = Field(default=None)
    n: int | None = Field(default=None, ge=1)

    def to_kwargs(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)
