"""Pydantic schemas for workspace CRUD."""
from __future__ import annotations

from pydantic import BaseModel, Field


class WorkspaceUpsertRequest(BaseModel):
    name: str
    archived: bool = False


class WorkspacePatchRequest(BaseModel):
    name: str | None = None
    archived: bool | None = None
    version: int = Field(..., description="Current version for optimistic locking")


class WorkspaceResponse(BaseModel):
    id: str
    name: str | None = None
    archived: bool = False
    deleted: bool = False
    created_at: str
    last_modified: str
    version: int


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceResponse]
    total: int
