from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ValidationIssue(BaseModel):
    code: str
    message: str
    path: str | None = None


class PromptVariableDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    label: str | None = None
    description: str | None = None
    required: bool = False
    default_value: Any = None
    input_type: str = "text"
    options: list[str] | None = None
    max_length: int | None = Field(default=None, ge=1)


class PromptBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    role: Literal["system", "developer", "user", "assistant"]
    kind: str | None = None
    content: str
    enabled: bool = True
    order: int
    is_template: bool = False


class PromptAssemblyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legacy_system_roles: list[str] = Field(default_factory=lambda: ["system", "developer"])
    legacy_user_roles: list[str] = Field(default_factory=lambda: ["user"])
    block_separator: str = "\n\n"


class PromptDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    format: Literal["structured"] = "structured"
    variables: list[PromptVariableDefinition] = Field(default_factory=list)
    blocks: list[PromptBlock] = Field(default_factory=list)
    assembly_config: PromptAssemblyConfig = Field(default_factory=PromptAssemblyConfig)
