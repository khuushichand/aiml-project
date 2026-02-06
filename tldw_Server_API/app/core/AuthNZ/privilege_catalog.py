"""
Utilities for loading and validating the privilege metadata catalog.

The catalog is defined in YAML (`tldw_Server_API/Config_Files/privilege_catalog.yaml`)
and enumerates scopes, feature flags, rate-limit classes, and ownership predicates.
This helper ensures catalog updates remain consistent and consumable throughout the
AuthNZ and privilege-mapping subsystems.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterable
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import yaml
from loguru import logger
from pydantic import AnyUrl, BaseModel, Field, ValidationError, model_validator, validator


def _default_catalog_path() -> Path:
    """
    Resolve the default privilege catalog path.

    Precedence:
      1. PRIVILEGE_CATALOG_FILE environment variable (if set)
      2. Repository-relative default: tldw_Server_API/Config_Files/privilege_catalog.yaml

    Relative paths are anchored to the project root to avoid dependence on the
    current working directory.
    """
    # Allow explicit override via environment variable
    raw = os.getenv("PRIVILEGE_CATALOG_FILE") or "tldw_Server_API/Config_Files/privilege_catalog.yaml"
    # Expand ~ and $VARS for convenience
    raw_expanded = os.path.expanduser(os.path.expandvars(str(raw)))
    candidate = Path(raw_expanded)

    if candidate.is_absolute():
        return candidate

    # Anchor relative paths to the detected project root
    try:
        from tldw_Server_API.app.core.Utils.Utils import get_project_root

        project_root = Path(get_project_root())
    except (ImportError, ModuleNotFoundError, AttributeError):
        # Conservative fallback: walk up from this file if Utils is unavailable
        project_root = Path(__file__).resolve().parents[4]

    return (project_root / candidate).resolve()


CATALOG_PATH = _default_catalog_path()


class OwnershipPredicateEntry(BaseModel):
    """Describes a coarse-grained ownership predicate used by privilege evaluations."""

    id: str
    evaluator: str
    description: str | None

    @validator("id")
    def validate_id(self, value: str) -> str:
        if not value.strip():
            raise ValueError("Ownership predicate id cannot be empty.")
        return value

    @validator("evaluator")
    def validate_evaluator(self, value: str) -> str:
        if not value.strip():
            raise ValueError("Ownership predicate evaluator cannot be empty.")
        return value


class RateLimitClassEntry(BaseModel):
    """Maps a rate limit class identifier to quota metadata."""

    id: str
    requests_per_min: int
    burst: int
    notes: str | None

    @validator("id")
    def validate_id(self, value: str) -> str:
        if not value.strip():
            raise ValueError("Rate limit class id cannot be empty.")
        return value

    @validator("requests_per_min", "burst")
    def validate_positive(self, value: int) -> int:
        if value < 0:
            raise ValueError("Rate limit quotas must be non-negative.")
        return value


class FeatureFlagEntry(BaseModel):
    """Defines a feature flag gating privilege scopes."""

    id: str
    description: str
    default_state: str
    allowed_roles: list[str] = Field(default_factory=list)
    expires_at: str | None

    @validator("id")
    def validate_id(self, value: str) -> str:
        if not value.strip():
            raise ValueError("Feature flag id cannot be empty.")
        return value

    @validator("default_state")
    def validate_state(self, value: str) -> str:
        allowed = {"enabled", "disabled"}
        if value not in allowed:
            raise ValueError(f"default_state must be one of {allowed}, got '{value}'.")
        return value


class ScopeEntry(BaseModel):
    """Represents a privilege scope that can be applied to routes and endpoints."""

    id: str
    description: str
    resource_tags: list[str] = Field(default_factory=list)
    sensitivity_tier: str
    rate_limit_class: str
    default_roles: list[str] = Field(default_factory=list)
    feature_flag_id: str | None
    ownership_predicates: list[str] = Field(default_factory=list)
    doc_url: AnyUrl | None

    @validator("id")
    def validate_id(self, value: str) -> str:
        if not value.strip():
            raise ValueError("Scope id cannot be empty.")
        return value

    @validator("sensitivity_tier")
    def validate_tier(self, value: str) -> str:
        allowed = {"low", "moderate", "high", "restricted"}
        if value not in allowed:
            raise ValueError(f"sensitivity_tier must be one of {allowed}, got '{value}'.")
        return value

    @validator("resource_tags", each_item=True)
    def validate_resource_tags(self, value: str) -> str:
        if not value.strip():
            raise ValueError("Resource tags cannot be empty strings.")
        return value

    @validator("default_roles", each_item=True)
    def validate_roles(self, value: str) -> str:
        if not value.strip():
            raise ValueError("Role names cannot be empty strings.")
        return value

    @validator("ownership_predicates", each_item=True)
    def validate_ownership_predicates(self, value: str) -> str:
        if not value.strip():
            raise ValueError("Ownership predicate identifiers cannot be empty strings.")
        return value


class PrivilegeCatalog(BaseModel):
    """Top-level catalog model with cross-field validation for references."""

    version: str
    updated_at: datetime
    scopes: list[ScopeEntry]
    feature_flags: list[FeatureFlagEntry] = Field(default_factory=list)
    rate_limit_classes: list[RateLimitClassEntry] = Field(default_factory=list)
    ownership_predicates: list[OwnershipPredicateEntry] = Field(default_factory=list)

    @validator("version")
    def validate_version(self, value: str) -> str:
        if not value.strip():
            raise ValueError("Catalog version cannot be empty.")
        return value

    @model_validator(mode="after")
    def validate_cross_references(self) -> PrivilegeCatalog:
        scopes: list[ScopeEntry] = self.scopes
        feature_flags: list[FeatureFlagEntry] = self.feature_flags
        limit_classes: list[RateLimitClassEntry] = self.rate_limit_classes
        ownership_predicates: list[OwnershipPredicateEntry] = self.ownership_predicates

        self._assert_unique([scope.id for scope in scopes], "scope id")
        feature_flag_ids = {flag.id for flag in feature_flags}
        self._assert_unique(feature_flag_ids, "feature flag id")
        rate_limit_ids = {rl.id for rl in limit_classes}
        self._assert_unique(rate_limit_ids, "rate limit class id")
        ownership_ids = {pred.id for pred in ownership_predicates}
        self._assert_unique(ownership_ids, "ownership predicate id")

        for scope in scopes:
            if scope.feature_flag_id and scope.feature_flag_id not in feature_flag_ids:
                raise ValueError(
                    f"Scope '{scope.id}' references unknown feature_flag_id '{scope.feature_flag_id}'."
                )
            if scope.rate_limit_class not in rate_limit_ids:
                raise ValueError(
                    f"Scope '{scope.id}' references unknown rate_limit_class '{scope.rate_limit_class}'."
                )
            missing_predicates = set(scope.ownership_predicates) - ownership_ids
            if missing_predicates:
                missing_str = ", ".join(sorted(missing_predicates))
                raise ValueError(
                    f"Scope '{scope.id}' references unknown ownership predicates: {missing_str}"
                )
        return self

    @staticmethod
    def _assert_unique(values: Iterable[str], label: str) -> None:
        seen: set[str] = set()
        for value in values:
            if value in seen:
                raise ValueError(f"Duplicate {label} detected: '{value}'")
            seen.add(value)


@lru_cache(maxsize=8)
def load_catalog(path: Path | None = None) -> PrivilegeCatalog:
    """
    Load and validate the privilege catalog from YAML.

    Args:
        path: Optional alternative path. Defaults to the canonical catalog path.

    Returns:
        PrivilegeCatalog: Parsed and validated catalog model.

    Raises:
        FileNotFoundError: If the catalog file does not exist.
        ValidationError: When catalog validation fails.
    """
    catalog_path = path or CATALOG_PATH
    if not catalog_path.exists():
        raise FileNotFoundError(f"Privilege catalog file not found: {catalog_path}")

    with catalog_path.open("r", encoding="utf-8") as handle:
        raw_data = yaml.safe_load(handle)

    try:
        return PrivilegeCatalog(**raw_data)
    except ValidationError as exc:
        logger.error("Privilege catalog validation failed: {}", exc)
        raise


def clear_privilege_catalog_cache() -> None:
    """Clear the load_catalog() LRU cache (used in tests or hot-reload scenarios)."""
    with contextlib.suppress(Exception):
        load_catalog.cache_clear()
