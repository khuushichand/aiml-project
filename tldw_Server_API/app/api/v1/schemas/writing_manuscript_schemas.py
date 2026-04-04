"""Pydantic schemas for manuscript management endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class ManuscriptProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="Project title")
    subtitle: str | None = Field(None, max_length=500, description="Project subtitle")
    author: str | None = Field(None, max_length=255, description="Author name")
    genre: str | None = Field(None, max_length=100, description="Genre")
    status: Literal["draft", "outlining", "writing", "revising", "complete", "archived"] = Field(
        "draft", description="Project status"
    )
    synopsis: str | None = Field(None, description="Project synopsis")
    target_word_count: int | None = Field(None, ge=0, description="Target word count")
    settings: dict[str, Any] | None = Field(None, description="Project settings JSON")
    id: str | None = Field(None, description="Optional client-provided UUID")


class ManuscriptProjectUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500, description="Project title")
    subtitle: str | None = Field(None, max_length=500, description="Project subtitle")
    author: str | None = Field(None, max_length=255, description="Author name")
    genre: str | None = Field(None, max_length=100, description="Genre")
    status: Literal["draft", "outlining", "writing", "revising", "complete", "archived"] | None = Field(
        None, description="Project status"
    )
    synopsis: str | None = Field(None, description="Project synopsis")
    target_word_count: int | None = Field(None, ge=0, description="Target word count")
    settings: dict[str, Any] | None = Field(None, description="Project settings JSON")


class ManuscriptProjectResponse(BaseModel):
    id: str
    title: str
    subtitle: str | None = None
    author: str | None = None
    genre: str | None = None
    status: str
    synopsis: str | None = None
    target_word_count: int | None = None
    settings_json: str | None = None
    word_count: int = 0
    created_at: datetime
    last_modified: datetime
    deleted: bool = False
    client_id: str
    version: int


class ManuscriptProjectListResponse(BaseModel):
    projects: list[ManuscriptProjectResponse]
    total: int


# ---------------------------------------------------------------------------
# Part
# ---------------------------------------------------------------------------


class ManuscriptPartCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="Part title")
    sort_order: float = Field(0, description="Sort order within the project")
    synopsis: str | None = Field(None, description="Part synopsis")
    id: str | None = Field(None, description="Optional client-provided UUID")


class ManuscriptPartUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500, description="Part title")
    sort_order: float | None = Field(None, description="Sort order within the project")
    synopsis: str | None = Field(None, description="Part synopsis")


class ManuscriptPartResponse(BaseModel):
    id: str
    project_id: str
    title: str
    sort_order: float
    synopsis: str | None = None
    word_count: int = 0
    created_at: datetime
    last_modified: datetime
    deleted: bool = False
    client_id: str
    version: int


# ---------------------------------------------------------------------------
# Chapter
# ---------------------------------------------------------------------------


class ManuscriptChapterCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="Chapter title")
    part_id: str | None = Field(None, description="Optional parent part ID")
    sort_order: float = Field(0, description="Sort order")
    synopsis: str | None = Field(None, description="Chapter synopsis")
    status: Literal["outline", "draft", "revising", "final"] = Field("draft", description="Chapter status")
    id: str | None = Field(None, description="Optional client-provided UUID")


class ManuscriptChapterUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500, description="Chapter title")
    part_id: str | None = Field(None, description="Parent part ID")
    sort_order: float | None = Field(None, description="Sort order")
    synopsis: str | None = Field(None, description="Chapter synopsis")
    status: Literal["outline", "draft", "revising", "final"] | None = Field(None, description="Chapter status")


class ManuscriptChapterResponse(BaseModel):
    id: str
    project_id: str
    part_id: str | None = None
    title: str
    sort_order: float
    synopsis: str | None = None
    pov_character_id: str | None = None
    word_count: int = 0
    status: str = "draft"
    created_at: datetime
    last_modified: datetime
    deleted: bool = False
    client_id: str
    version: int


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------


class ManuscriptSceneCreate(BaseModel):
    title: str = Field("Untitled Scene", min_length=1, max_length=500, description="Scene title")
    content: dict[str, Any] | None = Field(None, description="TipTap JSON content")
    content_plain: str = Field("", description="Plain-text content for word counting and search")
    synopsis: str | None = Field(None, description="Scene synopsis")
    sort_order: float = Field(0, description="Sort order within the chapter")
    status: Literal["outline", "draft", "revising", "final"] = Field("draft", description="Scene status")
    id: str | None = Field(None, description="Optional client-provided UUID")


class ManuscriptSceneUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500, description="Scene title")
    content: dict[str, Any] | None = Field(None, description="TipTap JSON content")
    content_plain: str | None = Field(None, description="Plain-text content")
    synopsis: str | None = Field(None, description="Scene synopsis")
    sort_order: float | None = Field(None, description="Sort order")
    status: Literal["outline", "draft", "revising", "final"] | None = Field(None, description="Scene status")


class ManuscriptSceneResponse(BaseModel):
    id: str
    chapter_id: str
    project_id: str
    title: str
    sort_order: float
    content_json: str | None = None
    content_plain: str | None = None
    synopsis: str | None = None
    word_count: int = 0
    pov_character_id: str | None = None
    status: str = "draft"
    created_at: datetime
    last_modified: datetime
    deleted: bool = False
    client_id: str
    version: int


# ---------------------------------------------------------------------------
# Structure tree
# ---------------------------------------------------------------------------


class SceneSummary(BaseModel):
    id: str
    title: str
    sort_order: float
    word_count: int = 0
    status: str = "draft"


class ChapterSummary(BaseModel):
    id: str
    title: str
    sort_order: float
    part_id: str | None = None
    word_count: int = 0
    status: str = "draft"
    scenes: list[SceneSummary] = Field(default_factory=list)


class PartSummary(BaseModel):
    id: str
    title: str
    sort_order: float
    word_count: int = 0
    chapters: list[ChapterSummary] = Field(default_factory=list)


class ManuscriptStructureResponse(BaseModel):
    project_id: str
    parts: list[PartSummary] = Field(default_factory=list)
    unassigned_chapters: list[ChapterSummary] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Reorder
# ---------------------------------------------------------------------------


class ReorderItem(BaseModel):
    id: str = Field(..., description="Entity ID")
    sort_order: float = Field(..., description="New sort order")
    new_parent_id: str | None = Field(None, description="Optional new parent ID (for reparenting chapters)")


class ReorderRequest(BaseModel):
    entity_type: Literal["parts", "chapters", "scenes"] = Field(
        ..., description="Type of entities being reordered"
    )
    items: list[ReorderItem] = Field(..., min_length=1, description="Items with new sort orders")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class ManuscriptSearchResult(BaseModel):
    id: str
    title: str
    chapter_id: str
    word_count: int = 0
    status: str = "draft"
    snippet: str | None = None


class ManuscriptSearchResponse(BaseModel):
    query: str
    results: list[ManuscriptSearchResult] = Field(default_factory=list)
