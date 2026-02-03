"""
User profile configuration catalog loader and validator.

The catalog is defined in YAML (tldw_Server_API/Config_Files/user_profile_catalog.yaml)
and enumerates profile/config keys, editability, and UI metadata.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import BaseModel, Field, ValidationError, model_validator, validator

_ALLOWED_EDITORS = {"user", "admin", "org_admin", "team_admin", "platform_admin"}


def _default_catalog_path() -> Path:
    """
    Resolve the default catalog path.

    Precedence:
      1. USER_PROFILE_CATALOG_FILE environment variable (if set)
      2. Repository-relative default: tldw_Server_API/Config_Files/user_profile_catalog.yaml
    """
    raw = os.getenv("USER_PROFILE_CATALOG_FILE") or "tldw_Server_API/Config_Files/user_profile_catalog.yaml"
    raw_expanded = os.path.expanduser(os.path.expandvars(str(raw)))
    candidate = Path(raw_expanded)

    if candidate.is_absolute():
        return candidate

    try:
        from tldw_Server_API.app.core.Utils.Utils import get_project_root

        project_root = Path(get_project_root())
    except (ImportError, ModuleNotFoundError, AttributeError):
        project_root = Path(__file__).resolve().parents[4]

    return (project_root / candidate).resolve()


CATALOG_PATH = _default_catalog_path()


class UserProfileCatalogEntry(BaseModel):
    """Defines a user profile config key and its metadata."""

    key: str
    label: str
    description: str | None = None
    type: str
    enum: list[Any] | None = None
    minimum: float | None = None
    maximum: float | None = None
    default: Any | None = None
    editable_by: list[str] = Field(default_factory=list)
    sensitivity: str
    ui: str | None = None
    deprecated: bool = False

    @validator("key", "label", "type", "sensitivity")
    def _not_empty(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("Field cannot be empty.")
        return value

    @validator("editable_by", each_item=True)
    def _validate_editable_by(cls, value: str) -> str:
        if value not in _ALLOWED_EDITORS:
            raise ValueError(f"Invalid editable_by role: {value}")
        return value


class UserProfileCatalog(BaseModel):
    """Top-level user profile catalog."""

    version: str
    updated_at: datetime
    entries: list[UserProfileCatalogEntry]

    @validator("version")
    def _validate_version(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Catalog version cannot be empty.")
        return value

    @model_validator(mode="after")
    def _validate_unique_keys(self) -> "UserProfileCatalog":
        keys = [entry.key for entry in self.entries]
        self._assert_unique(keys, "catalog key")
        return self

    @staticmethod
    def _assert_unique(values: Iterable[str], label: str) -> None:
        seen: set[str] = set()
        for value in values:
            if value in seen:
                raise ValueError(f"Duplicate {label} detected: '{value}'")
            seen.add(value)


@lru_cache(maxsize=8)
def _load_user_profile_catalog(catalog_path: Path) -> UserProfileCatalog:
    """
    Load and validate the user profile catalog from YAML.

    Args:
        catalog_path: Resolved catalog path.

    Returns:
        UserProfileCatalog: Parsed and validated catalog model.
    """
    if not catalog_path.exists():
        raise FileNotFoundError(f"User profile catalog file not found: {catalog_path}")

    with catalog_path.open("r", encoding="utf-8") as handle:
        raw_data = yaml.safe_load(handle)

    try:
        return UserProfileCatalog(**raw_data)
    except ValidationError as exc:
        logger.error("User profile catalog validation failed: {}", exc)
        raise


def load_user_profile_catalog(path: Path | None = None) -> UserProfileCatalog:
    """
    Load and validate the user profile catalog from YAML.

    Args:
        path: Optional alternative path. Defaults to the canonical catalog path.

    Returns:
        UserProfileCatalog: Parsed and validated catalog model.
    """
    catalog_path = path or CATALOG_PATH
    return _load_user_profile_catalog(catalog_path.resolve())


def clear_user_profile_catalog_cache() -> None:
    """Clear the load_user_profile_catalog() LRU cache (used in tests or hot-reload scenarios)."""
    try:
        _load_user_profile_catalog.cache_clear()
    except Exception:
        pass
