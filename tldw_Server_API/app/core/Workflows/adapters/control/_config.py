"""Pydantic config models for control flow adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class PromptConfig(BaseAdapterConfig):
    """Config for prompt rendering adapter."""

    template: str | None = Field(None, description="Jinja2 template to render (templated)")
    prompt: str | None = Field(None, description="Alias for template")
    variables: dict[str, Any] | None = Field(None, description="Variables to merge into context")
    simulate_delay_ms: int | None = Field(None, ge=0, description="Simulated delay for testing")
    force_error: bool | None = Field(False, description="Force error for testing")


class DelayConfig(BaseAdapterConfig):
    """Config for delay adapter."""

    milliseconds: int = Field(1000, ge=0, description="Delay duration in milliseconds")


class LogConfig(BaseAdapterConfig):
    """Config for log adapter."""

    message: str = Field(..., description="Message to log (templated)")
    level: Literal["debug", "info", "warning", "error"] = Field("info", description="Log level")


class BranchConfig(BaseAdapterConfig):
    """Config for conditional branching adapter."""

    condition: str = Field(..., description="Condition to evaluate (templated)")
    true_next: str | None = Field(None, description="Step ID if condition is true")
    false_next: str | None = Field(None, description="Step ID if condition is false")


class MapStepConfig(BaseAdapterConfig):
    """Config for substep within map adapter."""

    type: str = Field(..., description="Step type to execute for each item")
    config: dict[str, Any] = Field(default_factory=dict, description="Step configuration")


class MapConfig(BaseAdapterConfig):
    """Config for map (fan-out) adapter."""

    items: Any = Field(..., description="List of items or templated path to list")
    step: MapStepConfig = Field(..., description="Step to apply to each item")
    concurrency: int = Field(4, ge=1, le=100, description="Maximum concurrent executions")


class ParallelStepConfig(BaseAdapterConfig):
    """Config for step within parallel adapter."""

    type: str = Field(..., description="Step type to execute")
    config: dict[str, Any] = Field(default_factory=dict, description="Step configuration")


class ParallelConfig(BaseAdapterConfig):
    """Config for parallel execution adapter."""

    steps: list[ParallelStepConfig] = Field(..., description="Steps to execute in parallel")
    max_concurrency: int = Field(5, ge=1, le=50, description="Maximum concurrent steps")
    fail_fast: bool = Field(False, description="Stop on first error")


class BatchConfig(BaseAdapterConfig):
    """Config for batch processing adapter."""

    items: list[Any] = Field(..., description="Items to process in batches")
    batch_size: int = Field(10, ge=1, le=1000, description="Items per batch")
    step: dict[str, Any] = Field(..., description="Step to apply to each batch")
    delay_between_batches_ms: int = Field(0, ge=0, description="Delay between batches")


class CacheResultConfig(BaseAdapterConfig):
    """Config for result caching adapter."""

    key: str = Field(..., description="Cache key (templated)")
    ttl_seconds: int = Field(3600, ge=0, description="Cache TTL in seconds")
    step: dict[str, Any] = Field(..., description="Step to execute if cache miss")
    namespace: str | None = Field(None, description="Cache namespace")


class RetryConfig(BaseAdapterConfig):
    """Config for retry wrapper adapter."""

    step: dict[str, Any] = Field(..., description="Step to execute with retry")
    max_attempts: int = Field(3, ge=1, le=10, description="Maximum retry attempts")
    delay_ms: int = Field(1000, ge=0, description="Initial delay between retries")
    backoff_multiplier: float = Field(2.0, ge=1.0, le=5.0, description="Exponential backoff multiplier")
    retry_on_errors: list[str] | None = Field(None, description="Error patterns to retry on")


class CheckpointConfig(BaseAdapterConfig):
    """Config for checkpoint (state save) adapter."""

    name: str = Field(..., description="Checkpoint name")
    data: dict[str, Any] | None = Field(None, description="Data to save")
    include_context: bool = Field(True, description="Include current context in checkpoint")


class WorkflowCallConfig(BaseAdapterConfig):
    """Config for sub-workflow invocation adapter."""

    workflow_id: str = Field(..., description="ID of workflow to invoke")
    inputs: dict[str, Any] | None = Field(None, description="Inputs for sub-workflow")
    wait: bool = Field(True, description="Wait for completion")
    timeout_seconds: int = Field(300, ge=1, le=3600, description="Timeout for sub-workflow")
