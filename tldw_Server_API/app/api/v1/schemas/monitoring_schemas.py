from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WatchlistRule(BaseModel):
    pattern: str = Field(..., description="Literal or /regex/ pattern")
    category: Optional[str] = Field(None, description="Logical category, e.g., 'adult', 'violence', 'self_harm'")
    severity: Optional[str] = Field("info", description="info | warning | critical")
    note: Optional[str] = Field(None, description="Free-text note for admins")
    tags: Optional[List[str]] = Field(default=None, description="Optional tags")


class Watchlist(BaseModel):
    id: Optional[str] = Field(None, description="Watchlist ID (UUID). If absent on create, a new one is generated")
    name: str
    description: Optional[str] = None
    enabled: bool = True
    scope_type: str = Field("user", description="user | team | org")
    scope_id: str = Field(..., description="The corresponding subject id")
    rules: List[WatchlistRule] = Field(default_factory=list)


class WatchlistListResponse(BaseModel):
    watchlists: List[Watchlist]


class WatchlistUpsertResponse(BaseModel):
    watchlist: Watchlist
    status: str = Field("ok")


class WatchlistDeleteResponse(BaseModel):
    status: str
    id: str


class AlertItem(BaseModel):
    id: int
    created_at: str
    user_id: Optional[str] = None
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    source: str
    watchlist_id: Optional[str] = None
    rule_category: Optional[str] = None
    rule_severity: Optional[str] = None
    pattern: Optional[str] = None
    text_snippet: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_read: bool = False
    read_at: Optional[str] = None


class AlertsListResponse(BaseModel):
    items: List[AlertItem]
    total: Optional[int] = None  # Optional future enhancement


class MarkReadResponse(BaseModel):
    status: str
    id: int

