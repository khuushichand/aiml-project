"""Pydantic schemas for evaluation recipe registry and run persistence."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import RunStatus


class ReviewState(str, Enum):
    """Human review state for a recipe run."""

    NOT_REQUIRED = "not_required"
    NEEDS_REVIEW = "needs_review"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ConfidenceSummary(BaseModel):
    """Typed confidence summary persisted with recipe runs."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["aggregate", "bootstrap", "judge", "heuristic"] = "aggregate"
    confidence: float = Field(..., ge=0.0, le=1.0)
    sample_count: int = Field(default=0, ge=0)
    spread: float | None = Field(default=None, ge=0.0)
    margin: float | None = Field(default=None, ge=0.0)
    judge_agreement: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str | None = None


class RecommendationSlot(BaseModel):
    """Recommendation slot payload that can represent a null winner explicitly."""

    model_config = ConfigDict(extra="forbid")

    candidate_run_id: str | None = None
    reason_code: str | None = None
    explanation: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


RecipeEvaluationMode = Literal["fixed_context", "live_end_to_end"]
RecipeSupervisionMode = Literal["rubric", "reference_answer", "pairwise", "mixed"]
RecipeCandidateDimension = Literal[
    "generation_model",
    "prompt_variant",
    "formatting_citation_mode",
]


class RagAnswerQualityCapabilities(TypedDict, total=False):
    """Launch contract for the answer-quality RAG recipe."""

    evaluation_modes: list[RecipeEvaluationMode]
    supervision_modes: list[RecipeSupervisionMode]
    candidate_dimensions: list[RecipeCandidateDimension]


class RagAnswerQualityDefaultRunConfig(TypedDict, total=False):
    """Default run config for the answer-quality RAG recipe."""

    evaluation_mode: RecipeEvaluationMode
    supervision_mode: RecipeSupervisionMode
    candidate_dimensions: list[RecipeCandidateDimension]


class RecipeManifest(BaseModel):
    """Recipe manifest exposed by the registry."""

    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    recipe_version: str
    name: str
    description: str
    launchable: bool = True
    supported_modes: list[Literal["labeled", "unlabeled"]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    default_run_config: dict[str, Any] = Field(default_factory=dict)


class RecipeLaunchReadiness(BaseModel):
    """User-facing launch readiness for a recipe."""

    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    ready: bool
    can_enqueue_runs: bool
    can_reuse_completed_runs: bool = True
    runtime_checks: dict[str, bool] = Field(default_factory=dict)
    message: str | None = None


class RecipeDatasetValidationRequest(BaseModel):
    """Typed request payload for recipe dataset validation."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str | None = None
    dataset: list[dict[str, Any]] | None = None
    run_config: dict[str, Any] | None = None


class RecipeRunCreateRequest(RecipeDatasetValidationRequest):
    """Typed request payload for recipe-run creation."""

    run_config: dict[str, Any] = Field(default_factory=dict)
    force_rerun: bool = False


class RecipeDatasetValidationResponse(BaseModel):
    """Normalized validation payload with recipe-specific extension fields."""

    model_config = ConfigDict(extra="allow")

    valid: bool
    errors: list[str] = Field(default_factory=list)
    dataset_mode: str | None = None
    sample_count: int = Field(default=0, ge=0)
    dataset_snapshot_ref: str | None = None
    dataset_content_hash: str | None = None


class RecipeRunRecord(BaseModel):
    """Persistent recipe run record."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    recipe_id: str
    recipe_version: str
    status: RunStatus
    review_state: ReviewState = ReviewState.NOT_REQUIRED
    dataset_snapshot_ref: str | None = None
    dataset_content_hash: str | None = None
    confidence_summary: ConfidenceSummary | None = None
    recommendation_slots: dict[str, RecommendationSlot] = Field(default_factory=dict)
    child_run_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
