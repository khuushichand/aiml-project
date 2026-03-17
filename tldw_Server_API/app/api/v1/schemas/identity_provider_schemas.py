from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _blank_string_to_none(value: Any) -> Any:
    if isinstance(value, str) and not value.strip():
        return None
    return value


class IdentityProviderUpsertRequest(BaseModel):
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    provider_type: Literal["oidc"] = "oidc"
    owner_scope_type: Literal["global", "org"] = "global"
    owner_scope_id: int | None = Field(default=None, ge=1)
    enabled: bool = False
    display_name: str | None = Field(default=None, max_length=200)
    issuer: str = Field(..., min_length=1, max_length=1000)
    discovery_url: str | None = Field(default=None, max_length=1000)
    authorization_url: str | None = Field(default=None, max_length=1000)
    token_url: str | None = Field(default=None, max_length=1000)
    jwks_url: str | None = Field(default=None, max_length=1000)
    client_id: str | None = Field(default=None, max_length=500)
    client_secret_ref: str | None = Field(default=None, max_length=500)
    claim_mapping: dict[str, Any] = Field(default_factory=dict)
    provisioning_policy: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "display_name",
        "discovery_url",
        "authorization_url",
        "token_url",
        "jwks_url",
        "client_id",
        "client_secret_ref",
        mode="before",
    )
    @classmethod
    def normalize_blank_optionals(cls, value: Any) -> Any:
        return _blank_string_to_none(value)

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("issuer")
    @classmethod
    def normalize_issuer(cls, value: str) -> str:
        return value.strip()

    @field_validator("owner_scope_id")
    @classmethod
    def validate_owner_scope_id(cls, value: int | None, info) -> int | None:
        owner_scope_type = info.data.get("owner_scope_type", "global")
        if owner_scope_type == "org" and value is None:
            raise ValueError("owner_scope_id is required for org-scoped providers")
        if owner_scope_type == "global":
            return None
        return value

    model_config = ConfigDict(from_attributes=True)


class IdentityProviderResponse(BaseModel):
    id: int
    slug: str
    provider_type: str
    owner_scope_type: str
    owner_scope_id: int | None = None
    enabled: bool
    display_name: str | None = None
    issuer: str
    discovery_url: str | None = None
    authorization_url: str | None = None
    token_url: str | None = None
    jwks_url: str | None = None
    client_id: str | None = None
    client_secret_ref: str | None = None
    claim_mapping: dict[str, Any] = Field(default_factory=dict)
    provisioning_policy: dict[str, Any] = Field(default_factory=dict)
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class IdentityProviderListResponse(BaseModel):
    providers: list[IdentityProviderResponse]

    model_config = ConfigDict(from_attributes=True)


class IdentityProviderMappingPreviewRequest(BaseModel):
    claims: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class IdentityProviderMappingResult(BaseModel):
    subject: str | None = None
    email: str | None = None
    username: str | None = None
    groups: list[str] = Field(default_factory=list)
    derived_roles: list[str] = Field(default_factory=list)
    derived_org_ids: list[int] = Field(default_factory=list)
    derived_team_ids: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class IdentityProviderMappingPreviewResponse(IdentityProviderMappingResult):
    provider_id: int

    model_config = ConfigDict(from_attributes=True)


class IdentityProviderTestRequest(BaseModel):
    provider: IdentityProviderUpsertRequest

    model_config = ConfigDict(from_attributes=True)


class IdentityProviderTestResponse(BaseModel):
    ok: bool = True
    issuer: str
    authorization_url: str
    token_url: str
    jwks_url: str
    client_id: str
    warnings: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class IdentityProviderDryRunRequest(BaseModel):
    provider_id: int | None = Field(default=None, ge=1)
    provider: IdentityProviderUpsertRequest
    claims: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class IdentityProviderGrantSyncPreview(BaseModel):
    mode: str | None = None
    would_change: bool = False
    grant_org_ids: list[int] = Field(default_factory=list)
    grant_team_ids: list[int] = Field(default_factory=list)
    grant_roles: list[str] = Field(default_factory=list)
    revoke_org_ids: list[int] = Field(default_factory=list)
    revoke_team_ids: list[int] = Field(default_factory=list)
    revoke_roles: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class IdentityProviderDryRunResponse(BaseModel):
    provider: IdentityProviderTestResponse
    mapping: IdentityProviderMappingResult
    provisioning_action: Literal[
        "subject_already_linked",
        "link_existing_user",
        "create_new_user",
        "deny_missing_subject",
        "deny_missing_email_for_jit_create",
        "deny_email_collision",
        "deny_inactive_user",
        "deny_unlinked_user",
    ]
    matched_user_id: int | None = None
    identity_link_found: bool = False
    email_match_found: bool = False
    grant_sync: IdentityProviderGrantSyncPreview | None = None
    warnings: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
