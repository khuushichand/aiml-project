"""Schemas for Telegram bot configuration and admin link inventory."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

TELEGRAM_WEBHOOK_SECRET_MIN_LENGTH = 8


class TelegramBotConfigUpdate(BaseModel):
    """Update payload for Telegram bot configuration."""

    bot_token: str = Field(...)
    webhook_secret: str = Field(..., min_length=TELEGRAM_WEBHOOK_SECRET_MIN_LENGTH)
    bot_username: str | None = None
    enabled: bool = True

    @field_validator("bot_token", "webhook_secret", mode="before")
    @classmethod
    def _strip_and_require_nonempty(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned

    @field_validator("bot_username", mode="before")
    @classmethod
    def _normalize_bot_username(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.startswith("@"):
            cleaned = cleaned[1:]
        cleaned = cleaned.strip().lower()
        return cleaned or None


class TelegramBotConfigResponse(BaseModel):
    """Public Telegram bot configuration response."""

    ok: bool = True
    provider: Literal["telegram"] = "telegram"
    scope_type: Literal["org", "team"]
    scope_id: int
    bot_username: str
    enabled: bool


class TelegramLinkedActorItem(BaseModel):
    """Linked Telegram actor visible to workspace admins."""

    id: int
    scope_type: Literal["org", "team"]
    scope_id: int
    telegram_user_id: int
    auth_user_id: int
    telegram_username: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TelegramLinkedActorListResponse(BaseModel):
    """Admin response for linked Telegram actors in a workspace scope."""

    ok: bool = True
    scope_type: Literal["org", "team"]
    scope_id: int
    items: list[TelegramLinkedActorItem] = Field(default_factory=list)


class TelegramLinkedActorRevokeResponse(BaseModel):
    """Admin response for revoking a linked Telegram actor."""

    ok: bool = True
    deleted: bool
    id: int
    scope_type: Literal["org", "team"]
    scope_id: int


class TelegramWebhookActor(BaseModel):
    """Minimal Telegram actor payload used by webhook parsing."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: int | None = None
    username: str | None = None
    is_bot: bool | None = None


class TelegramWebhookChat(BaseModel):
    """Minimal Telegram chat payload used by webhook parsing."""

    model_config = ConfigDict(extra="allow")

    id: int | None = None
    type: str | None = None


class TelegramWebhookMessage(BaseModel):
    """Telegram message envelope."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    message_id: int | None = None
    chat: TelegramWebhookChat | None = None
    from_user: TelegramWebhookActor | None = Field(default=None, alias="from")
    text: str | None = None
    message_thread_id: int | None = None
    reply_to_message: TelegramWebhookMessage | None = None


class TelegramWebhookCallbackQuery(BaseModel):
    """Telegram callback query envelope."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str | None = None
    from_user: TelegramWebhookActor | None = Field(default=None, alias="from")
    message: TelegramWebhookMessage | None = None
    data: str | None = None


class TelegramWebhookUpdate(BaseModel):
    """Validated Telegram webhook payload."""

    model_config = ConfigDict(extra="allow")

    update_id: StrictInt
    message: TelegramWebhookMessage | None = None
    callback_query: TelegramWebhookCallbackQuery | None = None


TelegramWebhookMessage.model_rebuild()
