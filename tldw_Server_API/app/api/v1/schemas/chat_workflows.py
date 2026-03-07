from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _strip_required(value: str, *, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty")
    return stripped


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class ChatWorkflowTemplateStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    step_index: int = Field(..., ge=0)
    label: str | None = None
    base_question: str = Field(..., min_length=1)
    question_mode: Literal["stock", "llm_phrased"] = "stock"
    phrasing_instructions: str | None = None
    context_refs: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("id", "base_question")
    @classmethod
    def _strip_required_fields(cls, value: str, info) -> str:
        return _strip_required(value, field_name=info.field_name)

    @field_validator("label", "phrasing_instructions", mode="before")
    @classmethod
    def _strip_optional_fields(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("question_mode", mode="before")
    @classmethod
    def _normalize_question_mode(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower().replace("-", "_")
        return value


class ChatWorkflowTemplateDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1)
    description: str | None = None
    version: int = Field(default=1, ge=1)
    steps: list[ChatWorkflowTemplateStep] = Field(..., min_length=1)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        return _strip_required(value, field_name="title")

    @field_validator("description", mode="before")
    @classmethod
    def _strip_description(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class ChatWorkflowTemplateCreate(ChatWorkflowTemplateDraft):
    pass


class ChatWorkflowTemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    steps: list[ChatWorkflowTemplateStep] | None = None
    status: Literal["active", "archived"] | None = None

    @field_validator("title", mode="before")
    @classmethod
    def _strip_optional_title(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("description", mode="before")
    @classmethod
    def _strip_optional_description(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "ChatWorkflowTemplateUpdate":
        if (
            self.title is None
            and self.description is None
            and self.steps is None
            and self.status is None
        ):
            raise ValueError("at least one template field must be provided")
        return self


class GenerateDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(..., min_length=1)
    base_question: str | None = None
    desired_step_count: int = Field(default=4, ge=1, le=12)
    context_refs: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("goal")
    @classmethod
    def _strip_goal(cls, value: str) -> str:
        return _strip_required(value, field_name="goal")

    @field_validator("base_question", mode="before")
    @classmethod
    def _strip_base_question(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class GenerateDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_draft: ChatWorkflowTemplateDraft


class StartRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: int | None = Field(default=None, ge=1)
    template_draft: ChatWorkflowTemplateDraft | None = None
    selected_context_refs: list[dict[str, Any]] = Field(default_factory=list)
    question_renderer_model: str | None = None

    @field_validator("question_renderer_model", mode="before")
    @classmethod
    def _strip_question_renderer_model(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @model_validator(mode="after")
    def _validate_template_source(self) -> "StartRunRequest":
        has_template_id = self.template_id is not None
        has_template_draft = self.template_draft is not None
        if has_template_id == has_template_draft:
            raise ValueError("provide exactly one of template_id or template_draft")
        return self


class SubmitAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_index: int = Field(..., ge=0)
    answer_text: str = Field(..., min_length=1)
    idempotency_key: str | None = None

    @field_validator("answer_text")
    @classmethod
    def _strip_answer(cls, value: str) -> str:
        return _strip_required(value, field_name="answer_text")

    @field_validator("idempotency_key", mode="before")
    @classmethod
    def _strip_idempotency_key(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class ContinueChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str


class ChatWorkflowTemplateResponse(ChatWorkflowTemplateDraft):
    id: int
    status: str = "active"
    created_at: str | None = None
    updated_at: str | None = None


class ChatWorkflowAnswerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    step_index: int
    displayed_question: str
    answer_text: str
    question_generation_meta: dict[str, Any] = Field(default_factory=dict)
    answered_at: str | None = None


class ChatWorkflowRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    template_id: int | None = None
    template_version: int
    status: str
    current_step_index: int
    started_at: str | None = None
    completed_at: str | None = None
    canceled_at: str | None = None
    free_chat_conversation_id: str | None = None
    selected_context_refs: list[dict[str, Any]] = Field(default_factory=list)
    current_question: str | None = None
    answers: list[ChatWorkflowAnswerResponse] = Field(default_factory=list)
