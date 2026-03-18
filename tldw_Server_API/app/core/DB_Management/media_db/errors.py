"""Shared Media DB error types for extracted package modules."""

from __future__ import annotations

from typing import Any


class DatabaseError(Exception):
    """Base exception for database related errors."""


class SchemaError(DatabaseError):
    """Exception for schema version mismatches or migration failures."""


class InputError(ValueError):
    """Custom exception for input validation errors."""


class ConflictError(DatabaseError):
    """Indicates a conflict due to concurrent modification (version mismatch)."""

    def __init__(
        self,
        message: str = "Conflict detected: Record modified concurrently.",
        entity: str | None = None,
        identifier: Any = None,
    ) -> None:
        super().__init__(message)
        self.entity = entity
        self.identifier = identifier

    def __str__(self) -> str:
        base = super().__str__()
        details: list[str] = []
        if self.entity:
            details.append(f"Entity: {self.entity}")
        if self.identifier:
            details.append(f"ID: {self.identifier}")
        return f"{base} ({', '.join(details)})" if details else base
