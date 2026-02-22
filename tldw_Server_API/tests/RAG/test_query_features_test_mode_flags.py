import importlib

import pytest


pytestmark = pytest.mark.unit


def test_query_features_treats_test_mode_y_as_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_MODE", "y")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")
    monkeypatch.delenv("ALLOW_NLTK_DOWNLOADS", raising=False)

    module = importlib.import_module("tldw_Server_API.app.core.RAG.rag_service.query_features")
    module = importlib.reload(module)

    assert module._TEST_MODE is True
    assert module._ALLOW_NLTK_DOWNLOADS is False
