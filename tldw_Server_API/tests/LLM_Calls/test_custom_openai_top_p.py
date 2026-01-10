import pytest
from unittest.mock import patch

from tldw_Server_API.app.core.LLM_Calls.local_chat_calls import (
    chat_with_custom_openai,
    chat_with_custom_openai_2,
)


@pytest.mark.unit
def test_custom_openai_handler_accepts_topp(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": []}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            captured["json"] = json
            return FakeResp()

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter.http_client_factory",
        lambda *a, **k: FakeClient(),
    ):
        chat_with_custom_openai(
            input_data=[{"role": "user", "content": "ping"}],
            api_key="test-key",
            model="test-model",
            topp=0.33,
        )

    assert captured["json"]["top_p"] == 0.33


@pytest.mark.unit
def test_custom_openai_handler_prefers_maxp_when_both_provided(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": []}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            captured["json"] = json
            return FakeResp()

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter.http_client_factory",
        lambda *a, **k: FakeClient(),
    ):
        chat_with_custom_openai(
            input_data=[{"role": "user", "content": "ping"}],
            api_key="test-key",
            model="test-model",
            topp=0.12,
            maxp=0.45,
        )

    assert captured["json"]["top_p"] == 0.45


@pytest.mark.unit
def test_custom_openai_2_handler_accepts_topp(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": []}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            captured["json"] = json
            return FakeResp()

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter.http_client_factory",
        lambda *a, **k: FakeClient(),
    ):
        chat_with_custom_openai_2(
            input_data=[{"role": "user", "content": "ping"}],
            api_key="key-2",
            model="model-2",
            topp=0.27,
        )

    assert captured["json"]["top_p"] == 0.27
