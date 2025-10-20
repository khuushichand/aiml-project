from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl, validator


class ReadingSaveRequest(BaseModel):
    url: HttpUrl
    title: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    status: Optional[str] = Field(default="saved", description="saved|reading|read|archived")
    favorite: bool = False
    summary: Optional[str] = None
    content: Optional[str] = Field(default=None, description="Optional inline content override (testing/offline)")

    @validator("tags", pre=True, each_item=True)
    def _strip_tags(cls, value: str) -> str:
        return value.strip()


class ReadingItem(BaseModel):
    id: int
    media_id: Optional[int] = None
    title: str
    url: Optional[str] = None
    domain: Optional[str] = None
    summary: Optional[str] = None
    published_at: Optional[str] = None
    status: Optional[str] = None
    favorite: bool = False
    tags: List[str] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ReadingItemsListResponse(BaseModel):
    items: List[ReadingItem]
    total: int
    page: int
    size: int


class ReadingUpdateRequest(BaseModel):
    status: Optional[str] = Field(default=None, description="saved|reading|read|archived")
    favorite: Optional[bool] = None
    tags: Optional[List[str]] = None

    @validator("tags", pre=True, each_item=True)
    def _strip_tags(cls, value: str) -> str:
        return value.strip()
