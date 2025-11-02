from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Item(BaseModel):
    id: int
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
