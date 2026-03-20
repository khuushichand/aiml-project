import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.telegram_schemas import TelegramBotConfigUpdate


def test_telegram_bot_config_defaults_enabled_true():
    model = TelegramBotConfigUpdate(bot_token="123:abc", webhook_secret="secret-123")
    assert model.enabled is True
    assert model.bot_token == "123:abc"
    assert model.webhook_secret == "secret-123"


def test_telegram_bot_config_requires_bot_token_and_webhook_secret():
    with pytest.raises(ValidationError):
        TelegramBotConfigUpdate(webhook_secret="secret-123")

    with pytest.raises(ValidationError):
        TelegramBotConfigUpdate(bot_token="123:abc")


def test_telegram_bot_config_rejects_short_webhook_secret():
    with pytest.raises(ValidationError):
        TelegramBotConfigUpdate(bot_token="123:abc", webhook_secret="short")
