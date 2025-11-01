"""
Utilities for loading and validating the privilege metadata catalog.

The catalog is defined in YAML (`tldw_Server_API/Config_Files/privilege_catalog.yaml`)
and enumerates scopes, feature flags, rate-limit classes, and ownership predicates.
This helper ensures catalog updates remain consistent and consumable throughout the
AuthNZ and privilege-mapping subsystems.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set
from functools import lru_cache

from loguru import logger
from pydantic import AnyUrl, BaseModel, Field, ValidationError, model_validator, validator
import yaml


CATALOG_PATH = Path("tldw_Server_API/Config_Files/privilege_catalog.yaml")


class OwnershipPredicateEntry(BaseModel):
    """Describes a coarse-grained ownership predicate used by privilege evaluations."""

    id: str
    evaluator: str
    description: Optional[str]

    @validator("id")
    def validate_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Ownership predicate id cannot be empty.")
        return value

    @validator("evaluator")
    def validate_evaluator(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Ownership predicate evaluator cannot be empty.")
        return value


class RateLimitClassEntry(BaseModel):
    """Maps a rate limit class identifier to quota metadata."""

    id: str
    requests_per_min: int
    burst: int
    notes: Optional[str]

    @validator("id")
    def validate_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Rate limit class id cannot be empty.")
        return value

    @validator("requests_per_min", "burst")
    def validate_positive(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Rate limit quotas must be non-negative.")
        return value


class FeatureFlagEntry(BaseModel):
    """Defines a feature flag gating privilege scopes."""

    id: str
    description: str
    default_state: str
    allowed_roles: List[str] = Field(default_factory=list)
    expires_at: Optional[str]

    @validator("id")
    def validate_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Feature flag id cannot be empty.")
        return value

    @validator("default_state")
    def validate_state(cls, value: str) -> str:
        allowed = {"enabled", "disabled"}
        if value not in allowed:
            raise ValueError(f"default_state must be one of {allowed}, got '{value}'.")
        return value


class ScopeEntry(BaseModel):
    """Represents a privilege scope that can be applied to routes and endpoints."""

    id: str
    description: str
    resource_tags: List[str] = Field(default_factory=list)
    sensitivity_tier: str
    rate_limit_class: str
    default_roles: List[str] = Field(default_factory=list)
    feature_flag_id: Optional[str]
    ownership_predicates: List[str] = Field(default_factory=list)
    doc_url: Optional[AnyUrl]

    @validator("id")
    def validate_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Scope id cannot be empty.")
        return value

    @validator("sensitivity_tier")
    def validate_tier(cls, value: str) -> str:
        allowed = {"low", "moderate", "high", "restricted"}
        if value not in allowed:
            raise ValueError(f"sensitivity_tier must be one of {allowed}, got '{value}'.")
        return value

    @validator("resource_tags", each_item=True)
    def validate_resource_tags(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Resource tags cannot be empty strings.")
        return value

    @validator("default_roles", each_item=True)
    def validate_roles(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Role names cannot be empty strings.")
        return value

    @validator("ownership_predicates", each_item=True)
    def validate_ownership_predicates(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Ownership predicate identifiers cannot be empty strings.")
        return value


class PrivilegeCatalog(BaseModel):
    """Top-level catalog model with cross-field validation for references."""

    version: str
    updated_at: datetime
    scopes: List[ScopeEntry]
    feature_flags: List[FeatureFlagEntry] = Field(default_factory=list)
    rate_limit_classes: List[RateLimitClassEntry] = Field(default_factory=list)
    ownership_predicates: List[OwnershipPredicateEntry] = Field(default_factory=list)

    @validator("version")
    def validate_version(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Catalog version cannot be empty.")
        return value

    @model_validator(mode="after")
    def validate_cross_references(self) -> "PrivilegeCatalog":
        scopes: List[ScopeEntry] = self.scopes
        feature_flags: List[FeatureFlagEntry] = self.feature_flags
        limit_classes: List[RateLimitClassEntry] = self.rate_limit_classes
        ownership_predicates: List[OwnershipPredicateEntry] = self.ownership_predicates

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
        seen: Set[str] = set()
        for value in values:
            if value in seen:
                raise ValueError(f"Duplicate {label} detected: '{value}'")
            seen.add(value)


@lru_cache(maxsize=8)
def load_catalog(path: Optional[Path] = None) -> PrivilegeCatalog:
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
    try:
        load_catalog.cache_clear()
    except Exception:
        pass
