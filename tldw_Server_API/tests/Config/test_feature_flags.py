import os

from tldw_Server_API.app.core.config import settings


def test_feature_flags_present():
    # Basic presence and types
    assert "PERSONALIZATION_ENABLED" in settings
    assert isinstance(settings.get("PERSONALIZATION_ENABLED"), (bool, int))
    assert "PERSONA_ENABLED" in settings
    assert isinstance(settings.get("PERSONA_ENABLED"), (bool, int))
