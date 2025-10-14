# prompt_studio_optimization_requests.py
# Request models for optimization endpoints

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

class CompareStrategiesRequest(BaseModel):
    """Request model for comparing optimization strategies."""
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    prompt_id: int = Field(..., description="Prompt to optimize")
    # Accept optional project_id for back-compat with older clients/tests
    project_id: Optional[int] = Field(None, description="Project ID (optional; inferred from prompt if omitted)")
    test_case_ids: List[int] = Field(..., description="Test cases for evaluation")
    strategies: List[str] = Field(..., description="Strategies to compare")
    # Back-compat: accept config as alias for model_configuration
    model_configuration: Dict[str, Any] = Field(default_factory=dict, alias="config", description="Model configuration")
