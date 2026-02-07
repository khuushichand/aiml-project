"""Pydantic config models for utility adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class DiffChangeDetectorConfig(BaseAdapterConfig):
    """Config for diff/change detection adapter."""

    old_text: str = Field(..., description="Original text (templated)")
    new_text: str = Field(..., description="New text to compare (templated)")
    output_format: Literal["unified", "context", "side_by_side", "json"] = Field(
        "unified", description="Diff output format"
    )
    context_lines: int = Field(3, ge=0, le=10, description="Context lines around changes")


class DocumentDiffConfig(BaseAdapterConfig):
    """Config for document diff adapter."""

    file_uri_1: str = Field(..., description="file:// path to first document")
    file_uri_2: str = Field(..., description="file:// path to second document")
    output_format: Literal["unified", "html", "json"] = Field(
        "unified", description="Diff output format"
    )
    ignore_whitespace: bool = Field(False, description="Ignore whitespace differences")
    word_level: bool = Field(False, description="Word-level instead of line-level diff")


class DocumentMergeConfig(BaseAdapterConfig):
    """Config for document merge adapter."""

    documents: list[str] = Field(..., description="file:// URIs or text content to merge")
    separator: str = Field("\n\n", description="Separator between merged documents")
    include_headers: bool = Field(False, description="Include document headers/titles")
    output_format: Literal["text", "markdown", "html"] = Field(
        "text", description="Output format"
    )


class ContextBuildConfig(BaseAdapterConfig):
    """Config for context building adapter."""

    sources: list[dict[str, Any]] = Field(..., description="Context sources (text, files, etc.)")
    max_tokens: int | None = Field(None, ge=100, description="Maximum context tokens")
    strategy: Literal["truncate", "summarize", "prioritize"] = Field(
        "truncate", description="Strategy when exceeding max tokens"
    )
    separator: str = Field("\n\n---\n\n", description="Separator between sources")
    include_metadata: bool = Field(True, description="Include source metadata")


class EmbedConfig(BaseAdapterConfig):
    """Config for embedding generation adapter."""

    text: str = Field(..., description="Text to embed (templated)")
    model: str | None = Field(None, description="Embedding model")
    provider: str | None = Field(None, description="Embedding provider")
    dimensions: int | None = Field(None, ge=1, description="Output embedding dimensions")


class SandboxExecConfig(BaseAdapterConfig):
    """Config for sandbox code execution adapter."""

    code: str = Field(..., description="Code to execute (templated)")
    language: Literal["python", "javascript", "bash"] = Field(
        "python", description="Programming language"
    )
    timeout_seconds: int = Field(30, ge=1, le=300, description="Execution timeout")
    memory_mb: int = Field(256, ge=64, le=1024, description="Memory limit in MB")
    env_vars: dict[str, str] | None = Field(None, description="Environment variables")
    packages: list[str] | None = Field(None, description="Packages to install")


class ScreenshotCaptureConfig(BaseAdapterConfig):
    """Config for screenshot capture adapter."""

    url: str = Field(..., description="URL to capture (templated)")
    width: int = Field(1920, ge=320, le=3840, description="Viewport width")
    height: int = Field(1080, ge=240, le=2160, description="Viewport height")
    full_page: bool = Field(False, description="Capture full page scroll")
    format: Literal["png", "jpg", "webp"] = Field("png", description="Image format")
    wait_ms: int = Field(1000, ge=0, le=30000, description="Wait time before capture")
    selector: str | None = Field(None, description="CSS selector for specific element")


class ScheduleWorkflowConfig(BaseAdapterConfig):
    """Config for workflow scheduling adapter."""

    workflow_id: str = Field(..., description="Workflow ID to schedule")
    schedule: str = Field(..., description="Cron expression or schedule spec")
    inputs: dict[str, Any] | None = Field(None, description="Workflow inputs")
    enabled: bool = Field(True, description="Whether schedule is enabled")
    timezone: str = Field("UTC", description="Timezone for schedule")
    start_date: str | None = Field(None, description="Schedule start date (ISO format)")
    end_date: str | None = Field(None, description="Schedule end date (ISO format)")


class TimingStartConfig(BaseAdapterConfig):
    """Config for timing start adapter."""

    name: str | None = Field(None, description="Name for this timing measurement")


class TimingStopConfig(BaseAdapterConfig):
    """Config for timing stop adapter."""

    name: str | None = Field(None, description="Name of timing measurement to stop")
    format: Literal["ms", "s", "human"] = Field("ms", description="Duration format")
