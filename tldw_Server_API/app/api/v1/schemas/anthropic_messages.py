from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AnthropicContentBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(..., description="Block type, e.g. 'text', 'image', 'tool_use', 'tool_result'.")
    text: str | None = None
    source: dict[str, Any] | None = None
    id: str | None = None
    name: str | None = None
    input: Any | None = None
    content: Any | None = None
    tool_use_id: str | None = None
    is_error: bool | None = None


class AnthropicMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: Literal["user", "assistant"]
    content: str | list[AnthropicContentBlock]


class AnthropicTool(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = None


class AnthropicMessagesRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[AnthropicMessage]
    max_tokens: int | None = None
    system: str | list[AnthropicContentBlock] | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    stop_sequences: list[str] | None = None
    stream: bool | None = False
    tools: list[AnthropicTool] | None = None
    tool_choice: str | dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    # Extension: allow explicit provider selection when model has no prefix
    api_provider: str | None = Field(
        None,
        description="[Extension] Target LLM provider (e.g., 'anthropic', 'llama.cpp').",
    )


class AnthropicCountTokensRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[AnthropicMessage]
    system: str | list[AnthropicContentBlock] | None = None
    tools: list[AnthropicTool] | None = None
    tool_choice: str | dict[str, Any] | None = None
    api_provider: str | None = Field(
        None,
        description="[Extension] Target LLM provider (e.g., 'anthropic', 'llama.cpp').",
    )
