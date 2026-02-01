"""Base types and protocols for workflow adapters.

This module defines the base Pydantic models and type aliases used by adapters.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field


class AdapterContext(BaseModel):
    """Standard context passed to all adapters.

    This model defines the expected structure of the context dict passed to adapters.
    Adapters can access these fields for user/tenant info, previous step outputs, etc.
    """

    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    run_id: Optional[str] = None
    step_run_id: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    prev: Dict[str, Any] = Field(default_factory=dict)
    last: Dict[str, Any] = Field(default_factory=dict)
    secrets: Dict[str, str] = Field(default_factory=dict)
    workflow_metadata: Dict[str, Any] = Field(default_factory=dict)
    workflow_mcp_policy: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"  # Allow is_cancelled, add_artifact, etc.


class BaseAdapterConfig(BaseModel):
    """Base config model for adapters.

    Adapters can extend this with specific fields. The base config allows
    extra fields to support forward compatibility.
    """

    timeout_seconds: Optional[int] = Field(None, description="Step timeout in seconds")
    save_artifact: Optional[bool] = Field(False, description="Whether to save output as artifact")

    class Config:
        extra = "allow"  # Allow additional fields


# Type aliases for adapter signatures
AdapterFunc = Callable[[Dict[str, Any], Dict[str, Any]], Any]
"""Type alias for adapter function signature: async (config, context) -> result"""

AdapterResult = Dict[str, Any]
"""Type alias for adapter return value"""
