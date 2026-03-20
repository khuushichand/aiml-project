"""Schemas for Telegram bot configuration."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

TELEGRAM_WEBHOOK_SECRET_MIN_LENGTH = 8


class TelegramBotConfigUpdate(BaseModel):
    """Update payload for Telegram bot configuration."""

    bot_token: str = Field(...)
    webhook_secret: str = Field(..., min_length=TELEGRAM_WEBHOOK_SECRET_MIN_LENGTH)
    enabled: bool = True

    @field_validator("bot_token", "webhook_secret", mode="before")
    @classmethod
    def _strip_and_require_nonempty(cls, value):
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned


class TelegramBotConfigResponse(BaseModel):
    """Public Telegram bot configuration response."""

    ok: bool = True
    provider: Literal["telegram"] = "telegram"
    scope_type: Literal["org", "team"]
    scope_id: int
    bot_username: str
    enabled: bool
