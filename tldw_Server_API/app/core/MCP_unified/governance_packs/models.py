from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class GovernancePackManifest(BaseModel):
    pack_id: str
    pack_version: str
    pack_schema_version: int
    capability_taxonomy_version: int
    adapter_contract_version: int
    title: str
    description: str | None = None
    authors: list[str] = Field(default_factory=list)
    compatible_runtime_targets: list[str] = Field(default_factory=list)


class CapabilitySet(BaseModel):
    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)


class CapabilityProfile(BaseModel):
    profile_id: str
    name: str
    description: str | None = None
    capabilities: CapabilitySet = Field(default_factory=CapabilitySet)
    approval_intent: str
    environment_requirements: list[str] = Field(default_factory=list)


class ApprovalTemplate(BaseModel):
    approval_template_id: str
    name: str
    mode: str


class PersonaTemplate(BaseModel):
    persona_template_id: str
    name: str
    description: str | None = None
    capability_profile_id: str
    approval_template_id: str
    persona_traits: list[str] = Field(default_factory=list)


class AssignmentTemplate(BaseModel):
    assignment_template_id: str
    target_type: str
    capability_profile_id: str
    persona_template_id: str | None = None
    approval_template_id: str | None = None


@dataclass
class GovernancePack:
    source_path: Path
    manifest: GovernancePackManifest
    profiles: list[CapabilityProfile] = field(default_factory=list)
    approvals: list[ApprovalTemplate] = field(default_factory=list)
    personas: list[PersonaTemplate] = field(default_factory=list)
    assignments: list[AssignmentTemplate] = field(default_factory=list)
    raw_profiles: list[dict[str, Any]] = field(default_factory=list)
    raw_approvals: list[dict[str, Any]] = field(default_factory=list)
    raw_personas: list[dict[str, Any]] = field(default_factory=list)
    raw_assignments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class GovernancePackValidationResult:
    manifest: GovernancePackManifest | None
    errors: list[str] = field(default_factory=list)
