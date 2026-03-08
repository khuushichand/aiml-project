"""Checkpoint patch validation helpers for deep research review steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        candidate = str(item or "").strip()
        if candidate and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _normalize_stop_criteria(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, int] = {}
    for key in ("min_cited_sections", "min_sources"):
        raw = value.get(key)
        if raw is None:
            continue
        try:
            number = int(raw)
        except (TypeError, ValueError):
            continue
        if number >= 0:
            normalized[key] = number
    return normalized


def _proposed_outline_sections(proposed_payload: dict[str, Any]) -> list[dict[str, str]]:
    outline = proposed_payload.get("outline")
    if not isinstance(outline, dict):
        return []
    sections = outline.get("sections")
    if not isinstance(sections, list):
        return []
    normalized_sections: list[dict[str, str]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "").strip()
        focus_area = str(section.get("focus_area") or "").strip()
        if title and focus_area:
            normalized_sections.append({"title": title, "focus_area": focus_area})
    return normalized_sections


class _StopCriteriaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_cited_sections: int | None = Field(default=None, ge=0)
    min_sources: int | None = Field(default=None, ge=0)


class _PlanReviewPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus_areas: list[str] | None = None
    constraints: list[str] | None = None
    open_questions: list[str] | None = None
    stop_criteria: _StopCriteriaPatch | None = None

    @field_validator("focus_areas", "constraints", "open_questions", mode="before")
    @classmethod
    def _normalize_lists(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        return _normalize_string_list(value)


class _SourcesRecollectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    need_primary_sources: bool = False
    need_contradictions: bool = False
    guidance: str = ""

    @field_validator("guidance", mode="before")
    @classmethod
    def _normalize_guidance(cls, value: Any) -> str:
        return str(value or "").strip()


class _SourcesReviewPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pinned_source_ids: list[str] = Field(default_factory=list)
    dropped_source_ids: list[str] = Field(default_factory=list)
    prioritized_source_ids: list[str] = Field(default_factory=list)
    recollect: _SourcesRecollectPatch = Field(default_factory=_SourcesRecollectPatch)

    @field_validator("pinned_source_ids", "dropped_source_ids", "prioritized_source_ids", mode="before")
    @classmethod
    def _normalize_lists(cls, value: Any) -> list[str]:
        return _normalize_string_list(value)

    @model_validator(mode="after")
    def _validate_disjoint_sets(self) -> "_SourcesReviewPatch":
        overlap = set(self.pinned_source_ids) & set(self.dropped_source_ids)
        if overlap:
            raise ValueError(
                "pinned_source_ids and dropped_source_ids must be disjoint: "
                + ", ".join(sorted(overlap))
            )
        return self


class _OutlineReviewSectionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1)
    focus_area: str = Field(..., min_length=1)

    @field_validator("title", "focus_area", mode="before")
    @classmethod
    def _normalize_text(cls, value: Any) -> str:
        return str(value or "").strip()


class _OutlineReviewPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[_OutlineReviewSectionPatch]

    @model_validator(mode="after")
    def _validate_sections(self) -> "_OutlineReviewPatch":
        if not self.sections:
            raise ValueError("sections must not be empty")
        focus_areas = [section.focus_area for section in self.sections]
        if len(focus_areas) != len(set(focus_areas)):
            raise ValueError("focus_area values must be unique")
        return self


@dataclass(frozen=True)
class CheckpointPatchResult:
    normalized_patch: dict[str, Any]
    artifact_payload: dict[str, Any]


def _validate_model(checkpoint_type: str, model_cls: type[BaseModel], patch_payload: dict[str, Any]) -> BaseModel:
    try:
        return model_cls.model_validate(patch_payload)
    except ValidationError as exc:
        raise ValueError(f"invalid_checkpoint_patch:{checkpoint_type}:{exc}") from exc


def apply_checkpoint_patch(
    *,
    checkpoint_type: str,
    proposed_payload: dict[str, Any],
    patch_payload: dict[str, Any],
) -> CheckpointPatchResult:
    """Validate and materialize a user patch for a checkpoint approval."""
    proposed_payload = dict(proposed_payload or {})
    patch_payload = dict(patch_payload or {})

    if checkpoint_type == "plan_review":
        if not patch_payload:
            return CheckpointPatchResult(
                normalized_patch={},
                artifact_payload=dict(proposed_payload),
            )
        validated = _validate_model(checkpoint_type, _PlanReviewPatch, patch_payload)
        artifact_payload = dict(proposed_payload)
        if validated.focus_areas is not None:
            artifact_payload["focus_areas"] = list(validated.focus_areas)
        if validated.constraints is not None:
            artifact_payload["constraints"] = list(validated.constraints)
        if validated.open_questions is not None:
            artifact_payload["open_questions"] = list(validated.open_questions)
        if validated.stop_criteria is not None:
            artifact_payload["stop_criteria"] = {
                **_normalize_stop_criteria(proposed_payload.get("stop_criteria")),
                **validated.stop_criteria.model_dump(exclude_none=True),
            }
        return CheckpointPatchResult(
            normalized_patch=validated.model_dump(exclude_none=True),
            artifact_payload=artifact_payload,
        )

    if checkpoint_type == "sources_review":
        validated = _validate_model(checkpoint_type, _SourcesReviewPatch, patch_payload)
        source_inventory = proposed_payload.get("source_inventory")
        inventory_ids: set[str] = set()
        if isinstance(source_inventory, list):
            inventory_ids = {
                str(item.get("source_id") or "").strip()
                for item in source_inventory
                if isinstance(item, dict)
            }
        candidate_ids = (
            set(validated.pinned_source_ids)
            | set(validated.dropped_source_ids)
            | set(validated.prioritized_source_ids)
        )
        missing_ids = sorted(source_id for source_id in candidate_ids if source_id not in inventory_ids)
        if missing_ids:
            raise ValueError(
                "invalid_checkpoint_patch:sources_review:unknown source_ids: "
                + ", ".join(missing_ids)
            )
        invalid_prioritized = sorted(
            source_id
            for source_id in validated.prioritized_source_ids
            if source_id in set(validated.dropped_source_ids)
        )
        if invalid_prioritized:
            raise ValueError(
                "invalid_checkpoint_patch:sources_review:prioritized_source_ids must exclude dropped ids: "
                + ", ".join(invalid_prioritized)
            )
        artifact_payload = validated.model_dump()
        normalized_patch = artifact_payload if patch_payload else {}
        return CheckpointPatchResult(
            normalized_patch=normalized_patch,
            artifact_payload=artifact_payload,
        )

    if checkpoint_type == "outline_review":
        if not patch_payload:
            return CheckpointPatchResult(
                normalized_patch={},
                artifact_payload={"sections": _proposed_outline_sections(proposed_payload)},
            )
        validated = _validate_model(checkpoint_type, _OutlineReviewPatch, patch_payload)
        allowed_focus_areas = _normalize_string_list(proposed_payload.get("focus_areas"))
        if not allowed_focus_areas:
            allowed_focus_areas = [
                section["focus_area"]
                for section in _proposed_outline_sections(proposed_payload)
            ]
        invalid_focus_areas = sorted(
            {
                section.focus_area
                for section in validated.sections
                if section.focus_area not in allowed_focus_areas
            }
        )
        if invalid_focus_areas:
            raise ValueError(
                "invalid_checkpoint_patch:outline_review:unknown focus_area values: "
                + ", ".join(invalid_focus_areas)
            )
        artifact_payload = {
            "sections": [
                section.model_dump()
                for section in validated.sections
            ]
        }
        return CheckpointPatchResult(
            normalized_patch=artifact_payload,
            artifact_payload=artifact_payload,
        )

    raise ValueError(f"unsupported checkpoint type: {checkpoint_type}")


__all__ = ["CheckpointPatchResult", "apply_checkpoint_patch"]
