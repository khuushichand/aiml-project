from __future__ import annotations

from typing import Any, Dict, List, Optional, Union, Literal

from pydantic import BaseModel, ConfigDict, Field


class AnthropicContentBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(..., description="Block type, e.g. 'text', 'image', 'tool_use', 'tool_result'.")
    text: Optional[str] = None
    source: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    name: Optional[str] = None
    input: Optional[Any] = None
    content: Optional[Any] = None
    tool_use_id: Optional[str] = None
    is_error: Optional[bool] = None


class AnthropicMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: Literal["user", "assistant"]
    content: Union[str, List[AnthropicContentBlock]]


class AnthropicTool(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None


class AnthropicMessagesRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    messages: List[AnthropicMessage]
    max_tokens: Optional[int] = None
    system: Optional[Union[str, List[AnthropicContentBlock]]] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    stop_sequences: Optional[List[str]] = None
    stream: Optional[bool] = False
    tools: Optional[List[AnthropicTool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    # Extension: allow explicit provider selection when model has no prefix
    api_provider: Optional[str] = Field(
        None,
        description="[Extension] Target LLM provider (e.g., 'anthropic', 'llama.cpp').",
    )


class AnthropicCountTokensRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    messages: List[AnthropicMessage]
    system: Optional[Union[str, List[AnthropicContentBlock]]] = None
    tools: Optional[List[AnthropicTool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    api_provider: Optional[str] = Field(
        None,
        description="[Extension] Target LLM provider (e.g., 'anthropic', 'llama.cpp').",
    )
