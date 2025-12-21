from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict

from .chat_request_schemas import ChatCompletionMessageParam


class LlamaCppInferenceRequest(BaseModel):
    """OpenAI-style chat completion payload with permissive extras.

    Use extra='allow' so llama.cpp-specific fields can pass through without validation loss.
    """
    model_config = ConfigDict(extra='allow')

    model: Optional[str] = Field(default=None, description="Model identifier; may be ignored by active server")
    messages: Optional[List[ChatCompletionMessageParam]] = Field(default=None, description="Chat messages")
    stream: Optional[bool] = Field(default=None)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    stop: Optional[Union[str, List[str]]] = Field(default=None)
    user: Optional[str] = Field(default=None)
    n: Optional[int] = Field(default=None, ge=1)

    def to_kwargs(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)
