from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class Item(BaseModel):
    id: int
    content_item_id: Optional[int] = None
    media_id: Optional[int] = None
    title: str
    url: Optional[str] = None
    domain: Optional[str] = None
    summary: Optional[str] = None
    published_at: Optional[str] = None
    tags: List[str] = []
    type: Optional[str] = None


class ItemsListResponse(BaseModel):
    items: List[Item]
    total: int
    page: int
    size: int


BulkAction = Literal[
    "set_status",
    "set_favorite",
    "add_tags",
    "remove_tags",
    "replace_tags",
    "delete",
]


class ItemsBulkRequest(BaseModel):
    item_ids: List[int]
    action: BulkAction
    status: Optional[str] = None
    favorite: Optional[bool] = None
    tags: Optional[List[str]] = None
    hard: bool = False


class ItemsBulkResult(BaseModel):
    item_id: int
    success: bool
    error: Optional[str] = None


class ItemsBulkResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: List[ItemsBulkResult]
