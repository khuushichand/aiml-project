from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ALLOWED_CONVERSATION_STATES = ("in-progress", "resolved", "backlog", "non-viable")


class ConversationListItem(BaseModel):
    id: str = Field(..., description="Conversation ID")
    character_id: int | None = Field(None, description="Character ID associated with the conversation")
    title: str | None = Field(None, description="Conversation title")
    state: str = Field("in-progress", description="Lifecycle state of the conversation")
    topic_label: str | None = Field(None, description="Primary topic label")
    bm25_norm: float | None = Field(None, description="Normalized BM25 score (0-1)")
    last_modified: datetime = Field(..., description="Last modification timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    message_count: int = Field(0, description="Total messages in the conversation")
    keywords: list[str] = Field(default_factory=list, description="Keyword tags for the conversation")
    cluster_id: str | None = Field(None, description="Cluster/group identifier")
    source: str | None = Field(None, description="Source of the conversation")
    external_ref: str | None = Field(None, description="External reference ID")
    version: int = Field(1, description="Version number for optimistic locking")


class ConversationListPagination(BaseModel):
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Offset for pagination")
    total: int = Field(..., description="Total items matching filters")
    has_more: bool = Field(..., description="True when more items remain")


class ConversationListResponse(BaseModel):
    items: list[ConversationListItem] = Field(..., description="Conversation results")
    pagination: ConversationListPagination


class ConversationUpdateRequest(BaseModel):
    version: int = Field(..., description="Expected version for optimistic locking")
    state: str | None = Field(None, description="Lifecycle state for the conversation")
    topic_label: str | None = Field(None, description="Primary topic label for the conversation")
    keywords: list[str] | None = Field(None, description="Replace full keyword set (use [] to clear)")
    cluster_id: str | None = Field(None, description="Cluster/group identifier")
    source: str | None = Field(None, description="Source of the conversation")
    external_ref: str | None = Field(None, description="External reference/link")

    @field_validator("state")
    @classmethod
    def _validate_state(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("state cannot be empty")
        if normalized not in ALLOWED_CONVERSATION_STATES:
            raise ValueError(f"Invalid state '{value}'. Allowed: {', '.join(ALLOWED_CONVERSATION_STATES)}")
        return normalized

    @field_validator("keywords")
    @classmethod
    def _normalize_keywords(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = []
        seen = set()
        for v in value:
            if v is None:
                continue
            s = str(v).strip()
            if not s:
                continue
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(s)
        return cleaned


class ConversationMetadata(BaseModel):
    id: str = Field(..., description="Conversation ID")
    title: str | None = Field(None, description="Conversation title")
    state: str = Field("in-progress", description="Lifecycle state")
    topic_label: str | None = Field(None, description="Primary topic label")
    last_modified: datetime = Field(..., description="Last modification timestamp")


class ConversationTreeNode(BaseModel):
    id: str = Field(..., description="Message ID")
    role: str = Field(..., description="Message role (user/assistant/system)")
    content: str = Field("", description="Message content")
    created_at: datetime = Field(..., description="Message timestamp")
    children: list["ConversationTreeNode"] = Field(default_factory=list)
    truncated: bool = Field(False, description="True when descendants were omitted")


class ConversationTreePagination(BaseModel):
    limit: int = Field(..., description="Root threads per page")
    offset: int = Field(..., description="Root threads offset")
    total_root_threads: int = Field(..., description="Total root threads")
    has_more: bool = Field(..., description="True when more root threads remain")


class ConversationTreeResponse(BaseModel):
    conversation: ConversationMetadata
    root_threads: list[ConversationTreeNode]
    pagination: ConversationTreePagination
    depth_cap: int = Field(..., description="Applied depth cap")


class ChatAnalyticsBucket(BaseModel):
    bucket_start: datetime = Field(..., description="Bucket start date (UTC)")
    topic_label: str | None = Field(None, description="Topic label for the bucket")
    state: str = Field(..., description="Conversation state for the bucket")
    count: int = Field(..., description="Conversations in bucket")


class ChatAnalyticsPagination(BaseModel):
    limit: int = Field(..., description="Buckets per page")
    offset: int = Field(..., description="Bucket offset")
    total: int = Field(..., description="Total buckets")
    has_more: bool = Field(..., description="True when more buckets remain")


class ChatAnalyticsResponse(BaseModel):
    buckets: list[ChatAnalyticsBucket]
    pagination: ChatAnalyticsPagination
    bucket_granularity: Literal["day", "week"]
