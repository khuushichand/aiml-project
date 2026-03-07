"""Shared models for the deep research domain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResearchArtifact:
    id: str
    session_id: str
    artifact_name: str
    artifact_version: int
    storage_path: str
    content_type: str
    byte_size: int
    checksum: str
    phase: str
    job_id: str | None
    created_at: str


@dataclass(frozen=True)
class ResearchPlan:
    query: str
    focus_areas: list[str]
    source_policy: str
    autonomy_mode: str
    stop_criteria: dict[str, Any]
