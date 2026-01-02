"""Schemas for explicit feedback collection (chat + RAG)."""

from typing import List, Optional, Literal
from pydantic import BaseModel
try:
    from pydantic import model_validator  # type: ignore
except ImportError:
    model_validator = None  # type: ignore
from pydantic import ConfigDict
from ._compat import Field


class ExplicitFeedbackRequest(BaseModel):
    conversation_id: Optional[str] = Field(default=None, description="Conversation id for chat feedback")
    message_id: Optional[str] = Field(default=None, description="Message id for chat feedback")
    feedback_type: Literal["helpful", "relevance", "report"] = Field(..., description="Feedback category")
    helpful: Optional[bool] = Field(default=None, description="Helpful vote when feedback_type=helpful")
    relevance_score: Optional[int] = Field(default=None, ge=1, le=5, description="1-5 rating")
    document_ids: Optional[List[str]] = Field(default=None, description="Document ids rated")
    chunk_ids: Optional[List[str]] = Field(default=None, description="Chunk ids rated")
    corpus: Optional[str] = Field(default=None, description="Corpus/namespace for source-level feedback")
    issues: Optional[List[str]] = Field(default=None, description="Issue category ids")
    user_notes: Optional[str] = Field(default=None, description="Free-form notes")
    query: Optional[str] = Field(default=None, description="Query text (required when message_id is absent)")
    session_id: Optional[str] = Field(default=None, description="Client session id")
    idempotency_key: Optional[str] = Field(default=None, description="Optional dedupe key")

    if model_validator is not None:
        @model_validator(mode="before")
        def _require_query_for_rag_only(cls, values):  # type: ignore
            if isinstance(values, dict):
                message_id = values.get("message_id")
                query = values.get("query")
                if not message_id:
                    if query is None or str(query).strip() == "":
                        raise ValueError("query is required when message_id is not provided")
            return values

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "conversation_id": "C_...",
            "message_id": "M_...",
            "feedback_type": "helpful",
            "helpful": True,
            "relevance_score": 4,
            "issues": ["not_relevant"],
            "user_notes": "The answer was about a different feature.",
            "query": "how to reset auth",
        }
    })


class ExplicitFeedbackResponse(BaseModel):
    ok: bool = Field(default=True)
    feedback_id: Optional[str] = Field(default=None)
