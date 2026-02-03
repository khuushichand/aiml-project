# app/api/v1/schemas/skills_schemas.py
#
# Pydantic schemas for Skills API endpoints
#
# Imports
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

# 3rd-party Libraries
from pydantic import BaseModel, ConfigDict, Field, field_validator

#
# Local Imports
#
#######################################################################################################################
#
# Constants

# Skill name validation: lowercase letters, numbers, and hyphens only
SKILL_NAME_PATTERN = re.compile(r'^[a-z][a-z0-9-]{0,63}$')


#######################################################################################################################
#
# Schemas:

class SkillFrontmatter(BaseModel):
    """Parsed frontmatter from SKILL.md file."""
    name: str | None = Field(None, description="Skill identifier (lowercase, hyphens, max 64 chars)")
    description: str | None = Field(None, max_length=1000, description="What the skill does")
    argument_hint: str | None = Field(None, max_length=100, description="Hint shown in UI (e.g., '[issue-number]')")
    disable_model_invocation: bool = Field(False, description="If true, only user can invoke (not auto-invoked by LLM)")
    user_invocable: bool = Field(True, description="If false, hidden from user UI (background knowledge only)")
    allowed_tools: list[str] | None = Field(None, description="Tools allowed without permission when skill is active")
    model: str | None = Field(None, description="Override model for this skill")
    context: Literal["inline", "fork"] = Field("inline", description="'inline' or 'fork' (fork runs in isolated subagent)")

    model_config = ConfigDict(extra='ignore')


class SkillBase(BaseModel):
    """Base schema for skill data."""
    name: str = Field(..., min_length=1, max_length=64, description="Skill identifier")
    description: str | None = Field(None, max_length=1000, description="What the skill does")
    argument_hint: str | None = Field(None, max_length=100, description="Hint shown in UI")
    disable_model_invocation: bool = Field(False, description="If true, only user can invoke")
    user_invocable: bool = Field(True, description="If false, hidden from user UI")
    allowed_tools: list[str] | None = Field(None, description="Tools allowed during skill execution")
    model: str | None = Field(None, description="Override model for this skill")
    context: Literal["inline", "fork"] = Field("inline", description="Execution context mode")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip().lower()
        if not SKILL_NAME_PATTERN.match(value):
            raise ValueError(
                "Skill name must start with a letter, contain only lowercase letters, "
                "numbers, and hyphens, and be 1-64 characters long"
            )
        return value


class SkillCreate(BaseModel):
    """Schema for creating a new skill."""
    name: str = Field(..., min_length=1, max_length=64, description="Skill identifier")
    content: str = Field(..., min_length=1, max_length=500000, description="Full SKILL.md content with optional frontmatter")
    supporting_files: dict[str, str] | None = Field(
        None,
        description="Additional files (e.g., {'reference.md': '...content...'})"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip().lower()
        if not SKILL_NAME_PATTERN.match(value):
            raise ValueError(
                "Skill name must start with a letter, contain only lowercase letters, "
                "numbers, and hyphens, and be 1-64 characters long"
            )
        return value

    @field_validator("supporting_files")
    @classmethod
    def validate_supporting_files(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        for filename, content in value.items():
            # Validate filename format
            if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}$', filename):
                raise ValueError(f"Invalid supporting file name: {filename}")
            # Don't allow SKILL.md as supporting file
            if filename.lower() == "skill.md":
                raise ValueError("SKILL.md cannot be a supporting file")
            # Limit content size
            if len(content) > 500000:
                raise ValueError(f"Supporting file {filename} exceeds 500KB limit")
        return value


class SkillUpdate(BaseModel):
    """Schema for updating an existing skill."""
    content: str | None = Field(None, min_length=1, max_length=500000, description="Full SKILL.md content")
    supporting_files: dict[str, str] | None = Field(
        None,
        description="Additional files to update/add. Set value to None to remove a file."
    )

    @field_validator("supporting_files")
    @classmethod
    def validate_supporting_files(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        for filename, content in value.items():
            if content is None:
                continue  # None means delete the file
            if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}$', filename):
                raise ValueError(f"Invalid supporting file name: {filename}")
            if filename.lower() == "skill.md":
                raise ValueError("SKILL.md cannot be a supporting file")
            if len(content) > 500000:
                raise ValueError(f"Supporting file {filename} exceeds 500KB limit")
        return value


class SkillResponse(SkillBase):
    """Schema for skill responses."""
    id: str = Field(..., description="UUID of the skill")
    content: str = Field(..., description="SKILL.md content (markdown body without frontmatter)")
    supporting_files: dict[str, str] | None = Field(None, description="Additional files in the skill directory")
    directory_path: str = Field(..., description="Path to skill directory")
    created_at: datetime = Field(..., description="Timestamp of creation")
    last_modified: datetime = Field(..., description="Timestamp of last modification")
    version: int = Field(..., description="Version for optimistic locking")

    model_config = ConfigDict(from_attributes=True)


class SkillSummary(BaseModel):
    """Minimal skill info for listing."""
    name: str = Field(..., description="Skill identifier")
    description: str | None = Field(None, description="What the skill does")
    argument_hint: str | None = Field(None, description="Hint shown in UI")
    user_invocable: bool = Field(..., description="If false, hidden from user UI")
    disable_model_invocation: bool = Field(..., description="If true, only user can invoke")
    context: Literal["inline", "fork"] = Field(..., description="Execution context mode")

    model_config = ConfigDict(from_attributes=True)


class SkillsListResponse(BaseModel):
    """Response for listing skills."""
    skills: list[SkillSummary] = Field(..., description="List of skill summaries")
    count: int = Field(..., description="Number of skills in response")
    total: int = Field(..., description="Total number of skills")
    limit: int = Field(..., description="Pagination limit")
    offset: int = Field(..., description="Pagination offset")

    model_config = ConfigDict(from_attributes=True)


class SkillExecuteRequest(BaseModel):
    """Request to execute/preview a skill."""
    args: str | None = Field(None, max_length=10000, description="Arguments to pass to the skill")


class SkillExecutionResult(BaseModel):
    """Result of skill execution."""
    skill_name: str = Field(..., description="Name of the executed skill")
    rendered_prompt: str = Field(..., description="Prompt with arguments substituted")
    allowed_tools: list[str] | None = Field(None, description="Tools allowed for this skill")
    model_override: str | None = Field(None, description="Model override if specified")
    execution_mode: Literal["inline", "fork"] = Field(..., description="How the skill was executed")
    fork_output: str | None = Field(None, description="Output from fork execution (if applicable)")

    model_config = ConfigDict(from_attributes=True)


class SkillImportRequest(BaseModel):
    """Request to import a skill from text content."""
    name: str = Field(..., min_length=1, max_length=64, description="Skill name (will use frontmatter name if not provided)")
    content: str = Field(..., min_length=1, max_length=500000, description="SKILL.md content")
    supporting_files: dict[str, str] | None = Field(None, description="Additional files")
    overwrite: bool = Field(False, description="If true, overwrite existing skill with same name")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip().lower()
        if not SKILL_NAME_PATTERN.match(value):
            raise ValueError(
                "Skill name must start with a letter, contain only lowercase letters, "
                "numbers, and hyphens, and be 1-64 characters long"
            )
        return value


class SkillContextPayload(BaseModel):
    """Skill context for injection into chat."""
    available_skills: list[SkillSummary] = Field(..., description="Skills available for invocation")
    context_text: str = Field(..., description="Formatted text for LLM context injection")

    model_config = ConfigDict(from_attributes=True)


#
# End of skills_schemas.py
#######################################################################################################################
