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


@dataclass(frozen=True)
class ResearchSourceRecord:
    source_id: str
    focus_area: str
    source_type: str
    provider: str
    title: str
    url: str | None
    snippet: str
    published_at: str | None
    retrieved_at: str
    fingerprint: str
    trust_tier: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ResearchEvidenceNote:
    note_id: str
    source_id: str
    focus_area: str
    kind: str
    text: str
    citation_locator: str | None
    confidence: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ResearchCollectionResult:
    sources: list[ResearchSourceRecord]
    evidence_notes: list[ResearchEvidenceNote]
    collection_metrics: dict[str, Any]
    remaining_gaps: list[str]


@dataclass(frozen=True)
class ResearchOutlineSection:
    title: str
    focus_area: str
    source_ids: list[str]
    note_ids: list[str]


@dataclass(frozen=True)
class ResearchSynthesizedClaim:
    claim_id: str
    text: str
    focus_area: str
    source_ids: list[str]
    citations: list[dict[str, Any]]
    confidence: float


@dataclass(frozen=True)
class ResearchSynthesisResult:
    outline_sections: list[ResearchOutlineSection]
    claims: list[ResearchSynthesizedClaim]
    report_markdown: str
    unresolved_questions: list[str]
    synthesis_summary: dict[str, Any]
