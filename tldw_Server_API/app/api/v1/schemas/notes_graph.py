# app/api/v1/schemas/notes_graph.py
#
# Schemas for Notes Graph API (MVP)
# Aligns with Docs/Design/Graphing-Notes-PRD.md

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


class EdgeType(str, Enum):
    manual = "manual"
    wikilink = "wikilink"
    backlink = "backlink"
    tag_membership = "tag_membership"
    source_membership = "source_membership"


class GraphFormat(str, Enum):
    default = "default"
    cytoscape = "cytoscape"


class TimeRange(BaseModel):
    start: Optional[datetime] = Field(None, description="Start timestamp (inclusive) in ISO-8601")
    end: Optional[datetime] = Field(None, description="End timestamp (inclusive) in ISO-8601")


class GraphNode(BaseModel):
    id: str = Field(..., description="Opaque node identifier (e.g., note UUID or typed id)")
    type: Literal["note", "tag", "source"] = Field(..., description="Node entity type")
    label: str = Field(..., description="Human-readable label for rendering")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp (where applicable)")
    deleted: Optional[bool] = Field(
        None, description="Soft-deleted status (applies to notes; clients should dim/mark)"
    )
    degree: Optional[int] = Field(None, ge=0, description="Degree in the returned subgraph")
    tag_count: Optional[int] = Field(None, ge=0, description="Number of tags on a note (if computed)")
    primary_source_id: Optional[str] = Field(
        None, description="Primary source id for notes (when available)"
    )

    model_config = ConfigDict(from_attributes=True)


class GraphEdge(BaseModel):
    id: str = Field(..., description="Opaque edge id")
    source: str = Field(..., description="Source node id")
    target: str = Field(..., description="Target node id")
    type: EdgeType = Field(..., description="Edge type")
    directed: bool = Field(..., description="Whether the edge is directed")
    weight: Optional[float] = Field(1.0, ge=0.0, description="Optional weight; defaults to 1.0")
    label: Optional[str] = Field(None, description="Optional label for the edge")

    model_config = ConfigDict(from_attributes=True)


class GraphLimits(BaseModel):
    max_nodes: int = Field(..., ge=1)
    max_edges: int = Field(..., ge=0)
    max_degree: int = Field(..., ge=1)


class NoteGraphResponse(BaseModel):
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    truncated: bool = False
    truncated_by: List[str] = Field(default_factory=list)
    has_more: bool = False
    cursor: Optional[str] = None
    limits: GraphLimits

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nodes": [
                    {
                        "id": "note:123",
                        "type": "note",
                        "label": "My Note",
                        "created_at": "2025-01-01T12:00:00Z",
                        "degree": 2,
                        "tag_count": 3,
                        "primary_source_id": "source:yt:abcd",
                    },
                    {"id": "tag:ml", "type": "tag", "label": "ml"},
                    {
                        "id": "source:yt:abcd",
                        "type": "source",
                        "label": "YouTube: abcd",
                    },
                ],
                "edges": [
                    {
                        "id": "e:1",
                        "source": "note:123",
                        "target": "note:456",
                        "type": "manual",
                        "directed": False,
                        "weight": 1.0,
                    },
                    {
                        "id": "e:2",
                        "source": "note:123",
                        "target": "tag:ml",
                        "type": "tag_membership",
                        "directed": False,
                    },
                ],
                "truncated": False,
                "truncated_by": [],
                "has_more": False,
                "cursor": None,
                "limits": {"max_nodes": 300, "max_edges": 1200, "max_degree": 40},
            }
        }
    )


class NoteLinkCreate(BaseModel):
    to_note_id: str = Field(..., min_length=1, description="Target note id to link to")
    directed: bool = Field(False, description="Whether the link is directed; defaults to false")
    weight: Optional[float] = Field(1.0, ge=0.0, description="Optional weight of the link")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional metadata to attach to the link"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "to_note_id": "note:456",
                "directed": False,
                "weight": 1.0,
                "metadata": {"label": "related"},
            }
        }
    )


class NoteGraphRequest(BaseModel):
    center_note_id: Optional[str] = Field(
        default=None, description="Focal note id for ego expansion"
    )
    radius: int = Field(1, ge=1, le=2, description="Expansion radius; 1 by default, 2 allowed with caps")
    edge_types: Optional[List[EdgeType]] = Field(
        default=None,
        description="Edge types to include; accepts repeated values or CSV",
    )
    tag: Optional[str] = Field(default=None, description="Filter to notes with a specific tag id")
    source: Optional[str] = Field(default=None, description="Filter to notes with a specific source id")
    time_range: Optional[TimeRange] = None
    time_range_field: Literal["created_at", "updated_at"] = Field(
        "updated_at", description="Which timestamp field time_range applies to"
    )
    max_nodes: Optional[int] = Field(default=None, ge=1)
    max_edges: Optional[int] = Field(default=None, ge=0)
    max_degree: Optional[int] = Field(default=None, ge=1)
    format: GraphFormat = GraphFormat.default
    cursor: Optional[str] = None
    allow_heavy: bool = False

    @field_validator("edge_types", mode="before")
    @classmethod
    def _split_csv_edge_types(cls, v):
        if v is None:
            return v
        # Accept CSV string or repeated values that arrive as list[str]
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",") if p.strip()]
            return [EdgeType(p) for p in parts]
        if isinstance(v, list):
            out: List[EdgeType] = []
            for item in v:
                if isinstance(item, EdgeType):
                    out.append(item)
                elif isinstance(item, str):
                    out.append(EdgeType(item))
            return out
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "summary": "Ego graph for a note (default)",
                    "value": {
                        "center_note_id": "note:123",
                        "radius": 1,
                        "edge_types": [
                            "manual",
                            "wikilink",
                            "backlink",
                            "tag_membership",
                            "source_membership",
                        ],
                        "format": "default",
                        "max_nodes": 300,
                        "max_edges": 1200,
                        "max_degree": 40,
                    },
                }
            ]
        }
    )
