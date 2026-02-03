# prompt_studio_optimization_requests.py
# Request models for optimization endpoints

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CompareStrategiesRequest(BaseModel):
    """Request model for comparing optimization strategies."""
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    prompt_id: int = Field(..., description="Prompt to optimize")
    # Accept optional project_id for back-compat with older clients/tests
    project_id: Optional[int] = Field(None, description="Project ID (optional; inferred from prompt if omitted)")
    test_case_ids: list[int] = Field(..., description="Test cases for evaluation")
    strategies: list[str] = Field(..., description="Strategies to compare")
    # Back-compat: accept config as alias for model_configuration
    model_configuration: dict[str, Any] = Field(default_factory=dict, alias="config", description="Model configuration")


class OptimizationSimpleCreateRequest(BaseModel):
    """Minimal optimization job creation payload (compat endpoint)."""
    model_config = ConfigDict(extra='forbid')

    prompt_id: Optional[int] = None
    initial_prompt_id: Optional[int] = None
    config: dict[str, Any] = Field(default_factory=dict)
    # Back-compat: accept but ignore project_id and strategy fields
    project_id: Optional[int] = None
    strategy: Optional[str] = None

    @model_validator(mode="after")
    def _require_one_id(self):
        if not self.prompt_id and not self.initial_prompt_id:
            raise ValueError("One of prompt_id or initial_prompt_id must be provided")
        return self
