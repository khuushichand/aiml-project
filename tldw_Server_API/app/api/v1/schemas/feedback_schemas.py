"""Schemas for explicit feedback collection (chat + RAG)."""

from typing import Literal, Optional

from pydantic import BaseModel

try:
    from pydantic import model_validator  # type: ignore
except ImportError:
    model_validator = None  # type: ignore
try:
    from pydantic import root_validator  # type: ignore
except ImportError:
    root_validator = None  # type: ignore
from pydantic import ConfigDict

from ._compat import Field

_ERR_QUERY_REQUIRED = "query is required when message_id is not provided"
_ERR_HELPFUL_REQUIRED = "helpful is required when feedback_type is 'helpful'"
_ERR_RELEVANCE_REQUIRED = "relevance_score is required when feedback_type is 'relevance'"


def _validate_feedback_requirements(values: object) -> object:
    if not isinstance(values, dict):
        return values
    message_id = values.get("message_id")
    query = values.get("query")
    if not message_id and (query is None or str(query).strip() == ""):
        raise ValueError(_ERR_QUERY_REQUIRED)
    feedback_type = values.get("feedback_type")
    if feedback_type == "helpful" and values.get("helpful") is None:
        raise ValueError(_ERR_HELPFUL_REQUIRED)
    if feedback_type == "relevance" and values.get("relevance_score") is None:
        raise ValueError(_ERR_RELEVANCE_REQUIRED)
    return values


class ExplicitFeedbackRequest(BaseModel):
    conversation_id: Optional[str] = Field(default=None, description="Conversation id for chat feedback")
    message_id: Optional[str] = Field(default=None, description="Message id for chat feedback")
    feedback_type: Literal["helpful", "relevance", "report"] = Field(..., description="Feedback category")
    helpful: Optional[bool] = Field(default=None, description="Helpful vote when feedback_type=helpful")
    relevance_score: Optional[int] = Field(default=None, ge=1, le=5, description="1-5 rating")
    document_ids: Optional[list[str]] = Field(default=None, description="Document ids rated")
    chunk_ids: Optional[list[str]] = Field(default=None, description="Chunk ids rated")
    corpus: Optional[str] = Field(default=None, description="Corpus/namespace for source-level feedback")
    issues: Optional[list[str]] = Field(default=None, description="Issue category ids")
    user_notes: Optional[str] = Field(default=None, description="Free-form notes")
    query: Optional[str] = Field(default=None, description="Query text (required when message_id is absent)")
    session_id: Optional[str] = Field(default=None, description="Client session id")
    idempotency_key: Optional[str] = Field(default=None, description="Optional dedupe key")

    if model_validator is not None:
        @model_validator(mode="before")
        def _require_query_for_rag_only(cls, values):  # type: ignore
            return _validate_feedback_requirements(values)
    elif root_validator is not None:
        @root_validator(pre=True)  # type: ignore
        def _require_query_for_rag_only(cls, values):  # type: ignore
            return _validate_feedback_requirements(values)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "conversation_id": "C_...",
            "message_id": "M_...",
            "feedback_type": "helpful",
            "helpful": True,
            "relevance_score": 4,
            "document_ids": ["doc_1"],
            "chunk_ids": ["chunk_9"],
            "corpus": "media_db",
            "issues": ["not_relevant"],
            "user_notes": "The answer was about a different feature.",
            "query": "how to reset auth",
            "session_id": "sess_abc123",
            "idempotency_key": "fb_01HXYZ...",
        }
    })


class ExplicitFeedbackResponse(BaseModel):
    ok: bool = Field(default=True)
    feedback_id: Optional[str] = Field(default=None)
