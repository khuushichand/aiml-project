"""Pydantic config models for evaluation adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class EvaluationsConfig(BaseAdapterConfig):
    """Config for evaluations adapter."""

    eval_type: Literal["geval", "rag", "llm_judge", "custom"] = Field(
        "geval", description="Evaluation type"
    )
    input_text: str | None = Field(None, description="Input/query text (templated)")
    output_text: str | None = Field(None, description="Model output text (templated)")
    reference_text: str | None = Field(None, description="Reference/expected text")
    context: str | None = Field(None, description="Context for RAG evaluation")
    criteria: list[str] | None = Field(
        None, description="Evaluation criteria (relevance, coherence, etc.)"
    )
    provider: str | None = Field(None, description="LLM provider for evaluation")
    model: str | None = Field(None, description="Model for evaluation")
    rubric: dict[str, Any] | None = Field(None, description="Custom evaluation rubric")


class QuizEvaluateConfig(BaseAdapterConfig):
    """Config for quiz evaluation adapter."""

    questions: list[dict[str, Any]] = Field(..., description="Quiz questions with answers")
    user_answers: list[Any] = Field(..., description="User's answers")
    scoring: Literal["binary", "partial", "weighted"] = Field(
        "binary", description="Scoring method"
    )
    provide_feedback: bool = Field(True, description="Provide feedback for each answer")
    provider: str | None = Field(None, description="LLM provider for evaluation")
    model: str | None = Field(None, description="Model for evaluation")


class EvalReadabilityConfig(BaseAdapterConfig):
    """Config for readability evaluation adapter."""

    text: str = Field(..., description="Text to evaluate (templated)")
    metrics: list[Literal["flesch_kincaid", "gunning_fog", "smog", "coleman_liau", "ari", "dale_chall"]] = Field(
        ["flesch_kincaid", "gunning_fog"], description="Readability metrics to compute"
    )
    target_grade_level: int | None = Field(
        None, ge=1, le=20, description="Target reading grade level"
    )


class ContextWindowCheckConfig(BaseAdapterConfig):
    """Config for context window check adapter."""

    text: str = Field(..., description="Text to check (templated)")
    model: str = Field("gpt-4", description="Model to check context window for")
    max_percentage: float = Field(
        90.0, ge=0, le=100, description="Maximum allowed context usage percentage"
    )
    encoding: str | None = Field(None, description="Specific encoding to use")
