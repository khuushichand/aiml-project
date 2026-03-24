"""Typed schemas for normalized integrations control-plane payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

IntegrationProvider = Literal["slack", "discord", "telegram"]
IntegrationScope = Literal["personal", "workspace"]
IntegrationStatus = Literal["connected", "disconnected", "disabled", "degraded", "needs_config"]
IntegrationCommand = Literal["help", "ask", "rag", "summarize", "status"]
PersonalIntegrationProvider = Literal["slack", "discord"]


class IntegrationConnection(BaseModel):
    """One normalized connection or installation summary."""

    id: str
    provider: IntegrationProvider
    scope: IntegrationScope
    display_name: str
    status: IntegrationStatus
    enabled: bool
    connected_at: datetime | None = None
    updated_at: datetime | None = None
    health: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    actions: list[str] = Field(default_factory=list)


class IntegrationOverviewResponse(BaseModel):
    """Normalized list payload for integrations management surfaces."""

    scope: IntegrationScope
    items: list[IntegrationConnection] = Field(default_factory=list)


class PersonalIntegrationConnectResponse(BaseModel):
    """OAuth start payload for a personal integration connect or reconnect flow."""

    provider: PersonalIntegrationProvider
    connection_id: str
    status: Literal["ready"]
    auth_url: str
    auth_session_id: str
    expires_at: datetime


class PersonalIntegrationUpdateRequest(BaseModel):
    """Provider-level enable or disable action for a personal integration."""

    enabled: bool


class PersonalIntegrationDeleteResponse(BaseModel):
    """Delete response for a provider-level personal integration removal."""

    deleted: bool = True
    provider: PersonalIntegrationProvider
    connection_id: str


class SlackWorkspacePolicy(BaseModel):
    """Typed workspace policy for Slack integrations."""

    allowed_commands: list[IntegrationCommand] = Field(default_factory=list)
    channel_allowlist: list[str] = Field(default_factory=list)
    channel_denylist: list[str] = Field(default_factory=list)
    default_response_mode: Literal["ephemeral", "thread", "channel"]
    strict_user_mapping: bool = False
    service_user_id: str | None = None
    user_mappings: dict[str, str] = Field(default_factory=dict)
    workspace_quota_per_minute: int
    user_quota_per_minute: int
    status_scope: Literal["workspace", "workspace_and_user"]


class SlackWorkspacePolicyUpdate(BaseModel):
    """Typed update payload for Slack workspace policy."""

    allowed_commands: list[IntegrationCommand] | None = None
    channel_allowlist: list[str] | None = None
    channel_denylist: list[str] | None = None
    default_response_mode: Literal["ephemeral", "thread", "channel"] | None = None
    strict_user_mapping: bool | None = None
    service_user_id: str | None = None
    user_mappings: dict[str, str] | None = None
    workspace_quota_per_minute: int | None = None
    user_quota_per_minute: int | None = None
    status_scope: Literal["workspace", "workspace_and_user"] | None = None


class SlackWorkspacePolicyResponse(BaseModel):
    """Typed Slack workspace policy response for the control plane."""

    provider: Literal["slack"] = "slack"
    scope: Literal["workspace"] = "workspace"
    installation_ids: list[str] = Field(default_factory=list)
    uniform: bool = True
    policy: SlackWorkspacePolicy


class DiscordWorkspacePolicy(BaseModel):
    """Typed workspace policy for Discord integrations."""

    allowed_commands: list[IntegrationCommand] = Field(default_factory=list)
    channel_allowlist: list[str] = Field(default_factory=list)
    channel_denylist: list[str] = Field(default_factory=list)
    default_response_mode: Literal["ephemeral", "channel"]
    strict_user_mapping: bool = False
    service_user_id: str | None = None
    user_mappings: dict[str, str] = Field(default_factory=dict)
    guild_quota_per_minute: int
    user_quota_per_minute: int
    status_scope: Literal["guild", "guild_and_user"]


class DiscordWorkspacePolicyUpdate(BaseModel):
    """Typed update payload for Discord workspace policy."""

    allowed_commands: list[IntegrationCommand] | None = None
    channel_allowlist: list[str] | None = None
    channel_denylist: list[str] | None = None
    default_response_mode: Literal["ephemeral", "channel"] | None = None
    strict_user_mapping: bool | None = None
    service_user_id: str | None = None
    user_mappings: dict[str, str] | None = None
    guild_quota_per_minute: int | None = None
    user_quota_per_minute: int | None = None
    status_scope: Literal["guild", "guild_and_user"] | None = None


class DiscordWorkspacePolicyResponse(BaseModel):
    """Typed Discord workspace policy response for the control plane."""

    provider: Literal["discord"] = "discord"
    scope: Literal["workspace"] = "workspace"
    installation_ids: list[str] = Field(default_factory=list)
    uniform: bool = True
    policy: DiscordWorkspacePolicy
