# app/core/Skills/exceptions.py
#
# Skills-specific exceptions
#
"""
Skills Exceptions
=================

Custom exception hierarchy for the Skills module.
"""

from typing import Any, Optional


class SkillsError(Exception):
    """Base exception for Skills module errors."""

    def __init__(self, message: str, *, detail: Optional[Any] = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class SkillNotFoundError(SkillsError):
    """Raised when a skill is not found."""

    def __init__(self, skill_name: str, *, detail: Optional[str] = None) -> None:
        message = f"Skill not found: {skill_name}"
        if detail:
            message = f"{message} ({detail})"
        super().__init__(message, detail=detail)
        self.skill_name = skill_name


class SkillValidationError(SkillsError):
    """Raised when skill validation fails."""

    def __init__(self, message: str, *, field: Optional[str] = None, detail: Optional[Any] = None) -> None:
        super().__init__(message, detail=detail)
        self.field = field


class SkillConflictError(SkillsError):
    """Raised on concurrent modification or unique constraint violation."""

    def __init__(
        self,
        message: str,
        *,
        skill_name: Optional[str] = None,
        expected_version: Optional[int] = None,
        actual_version: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.skill_name = skill_name
        self.expected_version = expected_version
        self.actual_version = actual_version


class SkillParseError(SkillsError):
    """Raised when parsing SKILL.md content fails."""

    def __init__(self, message: str, *, line: Optional[int] = None, detail: Optional[str] = None) -> None:
        super().__init__(message, detail=detail)
        self.line = line


class SkillExecutionError(SkillsError):
    """Raised when skill execution fails."""

    def __init__(
        self,
        message: str,
        *,
        skill_name: Optional[str] = None,
        execution_mode: Optional[str] = None,
        detail: Optional[Any] = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.skill_name = skill_name
        self.execution_mode = execution_mode


class SkillStorageError(SkillsError):
    """Raised when skill file operations fail."""

    def __init__(self, message: str, *, path: Optional[str] = None, detail: Optional[str] = None) -> None:
        super().__init__(message, detail=detail)
        self.path = path
