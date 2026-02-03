"""Pydantic config models for LLM adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class LLMConfig(BaseAdapterConfig):
    """Config for LLM chat completion adapter."""

    provider: str | None = Field(None, description="LLM provider (openai, anthropic, etc.)")
    model: str | None = Field(None, description="Model name")
    prompt: str | None = Field(None, description="User prompt (templated)")
    messages: list[dict[str, Any]] | None = Field(None, description="Chat messages array")
    system_message: str | None = Field(None, description="System prompt")
    temperature: float = Field(0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: int | None = Field(None, ge=1, description="Maximum tokens to generate")
    top_p: float | None = Field(None, ge=0, le=1, description="Top-p sampling")
    frequency_penalty: float | None = Field(None, ge=-2, le=2, description="Frequency penalty")
    presence_penalty: float | None = Field(None, ge=-2, le=2, description="Presence penalty")
    stop: list[str] | None = Field(None, description="Stop sequences")
    stream: bool = Field(False, description="Enable streaming response")
    response_format: dict[str, Any] | None = Field(None, description="Response format (JSON mode, etc.)")


class ToolDefinition(BaseAdapterConfig):
    """Definition of a tool for LLM with tools."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: dict[str, Any] = Field(..., description="JSON Schema for tool parameters")


class LLMWithToolsConfig(BaseAdapterConfig):
    """Config for LLM with tool calling adapter."""

    provider: str | None = Field(None, description="LLM provider")
    model: str | None = Field(None, description="Model name")
    prompt: str | None = Field(None, description="User prompt (templated)")
    messages: list[dict[str, Any]] | None = Field(None, description="Chat messages array")
    system_message: str | None = Field(None, description="System prompt")
    tools: list[ToolDefinition] = Field(..., description="Available tools")
    tool_choice: Literal["auto", "none", "required"] | dict[str, Any] | None = Field(
        "auto", description="Tool choice strategy"
    )
    max_tool_rounds: int = Field(5, ge=1, le=20, description="Maximum tool call rounds")
    temperature: float = Field(0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: int | None = Field(None, ge=1, description="Maximum tokens to generate")


class LLMCompareConfig(BaseAdapterConfig):
    """Config for LLM comparison adapter."""

    prompt: str = Field(..., description="Prompt to send to all models (templated)")
    providers: list[dict[str, Any]] = Field(
        ..., description="List of provider/model configurations to compare"
    )
    system_message: str | None = Field(None, description="System prompt for all models")
    temperature: float = Field(0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: int | None = Field(None, ge=1, description="Maximum tokens to generate")
    compare_metrics: list[Literal["latency", "token_count", "cost"]] = Field(
        ["latency", "token_count"], description="Metrics to compare"
    )


class LLMCritiqueConfig(BaseAdapterConfig):
    """Config for LLM critique/evaluation adapter."""

    text: str = Field(..., description="Text to critique (templated)")
    criteria: list[str] = Field(
        ..., description="Criteria for evaluation (clarity, accuracy, etc.)"
    )
    rubric: dict[str, Any] | None = Field(None, description="Custom evaluation rubric")
    provider: str | None = Field(None, description="LLM provider for critique")
    model: str | None = Field(None, description="Model for critique")
    return_scores: bool = Field(True, description="Return numeric scores")
    return_suggestions: bool = Field(True, description="Return improvement suggestions")


class ModerationConfig(BaseAdapterConfig):
    """Config for content moderation adapter."""

    text: str = Field(..., description="Text to moderate (templated)")
    provider: Literal["openai", "anthropic", "local", "llm"] = Field(
        "openai", description="Moderation provider"
    )
    model: str | None = Field(None, description="Moderation model")
    categories: list[str] | None = Field(
        None, description="Categories to check (hate, violence, etc.)"
    )
    threshold: float = Field(0.5, ge=0, le=1, description="Flagging threshold")


class PolicyCheckConfig(BaseAdapterConfig):
    """Config for policy/PII check adapter."""

    text: str = Field(..., description="Text to check (templated)")
    policies: list[str] = Field(
        ..., description="Policies to check against (pii, profanity, etc.)"
    )
    action: Literal["flag", "redact", "block"] = Field(
        "flag", description="Action when policy violation found"
    )
    pii_types: list[str] | None = Field(
        None, description="PII types to detect (email, phone, ssn, etc.)"
    )


class TranslateConfig(BaseAdapterConfig):
    """Config for translation adapter."""

    text: str = Field(..., description="Text to translate (templated)")
    target_language: str = Field(..., description="Target language code (e.g., 'es', 'fr')")
    source_language: str | None = Field(
        None, description="Source language code (auto-detect if not specified)"
    )
    provider: str | None = Field(None, description="Translation provider")
    model: str | None = Field(None, description="Translation model")
    preserve_formatting: bool = Field(True, description="Preserve text formatting")
    glossary: dict[str, str] | None = Field(None, description="Custom translation glossary")
