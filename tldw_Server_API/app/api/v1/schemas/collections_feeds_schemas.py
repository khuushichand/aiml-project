from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, HttpUrl, validator

from tldw_Server_API.app.api.v1.schemas._compat import Field


class CollectionsFeedCreateRequest(BaseModel):
    url: HttpUrl = Field(example="https://example.com/feed.xml")
    name: Optional[str] = Field(default=None, example="Example Feed")
    tags: List[str] = Field(default_factory=list, example=["news", "tech"])
    schedule_expr: Optional[str] = Field(default=None, description="Cron expression for polling")
    timezone: Optional[str] = Field(default=None, description="Timezone for schedule (IANA or UTC+/-)")
    active: bool = Field(default=True, description="Whether the feed job is active")
    settings: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional watchlists source settings (rss/history prefs, limits)",
    )

    @validator("tags", pre=True, each_item=True)
    def _strip_tags(cls, value: str) -> str:
        return value.strip()


class CollectionsFeedUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, example="Example Feed")
    url: Optional[HttpUrl] = Field(default=None, example="https://example.com/feed.xml")
    tags: Optional[List[str]] = Field(default=None, example=["news", "tech"])
    schedule_expr: Optional[str] = Field(default=None, description="Cron expression for polling")
    timezone: Optional[str] = Field(default=None, description="Timezone for schedule (IANA or UTC+/-)")
    active: Optional[bool] = Field(default=None, description="Whether the feed job is active")
    settings: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional watchlists source settings (rss/history prefs, limits)",
    )

    @validator("tags", pre=True, each_item=True)
    def _strip_tags(cls, value: str) -> str:
        return value.strip()


class CollectionsFeed(BaseModel):
    id: int
    name: str
    url: str
    source_type: str = Field(example="rss")
    origin: str = Field(example="feed")
    tags: List[str] = Field(default_factory=list)
    active: bool
    settings: Optional[Dict[str, Any]] = None
    last_scraped_at: Optional[str] = None
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    defer_until: Optional[str] = None
    status: Optional[str] = None
    consec_not_modified: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    job_id: Optional[int] = None
    schedule_expr: Optional[str] = None
    timezone: Optional[str] = None
    job_active: Optional[bool] = None
    next_run_at: Optional[str] = None
    wf_schedule_id: Optional[str] = None


class CollectionsFeedsListResponse(BaseModel):
    items: List[CollectionsFeed]
    total: int
