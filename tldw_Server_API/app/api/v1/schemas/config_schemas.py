# config_schemas.py
"""Schemas for effective configuration diagnostics."""

from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field


class ConfigValue(BaseModel):
    """A config value with source tagging and redaction metadata."""

    value: Any = Field(..., description="Effective value (redacted when sensitive)")
    source: Literal["env", "config", "yaml", "default"] = Field(
        ..., description="Effective source tag"
    )
    redacted: bool = Field(False, description="Whether the value was redacted")


class EffectiveConfigResponse(BaseModel):
    """Response schema for effective config diagnostics."""

    config_root: str = Field(..., description="Resolved config root directory")
    config_file: Optional[str] = Field(None, description="Resolved config.txt path")
    prompts_dir: Optional[str] = Field(None, description="Resolved prompts directory")
    module_yaml: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Module YAML paths keyed by module name",
    )
    values: Dict[str, Dict[str, ConfigValue]] = Field(
        default_factory=dict,
        description="Effective config values by namespace",
    )
    unknown_sections: List[str] = Field(
        default_factory=list,
        description="Requested config sections that are not recognized",
    )
