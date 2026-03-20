"""Schemas for Telegram bot configuration."""

from pydantic import BaseModel, Field


class TelegramBotConfigUpdate(BaseModel):
    """Update payload for Telegram bot configuration."""

    bot_token: str = Field(...)
    webhook_secret: str = Field(...)
    enabled: bool = True
