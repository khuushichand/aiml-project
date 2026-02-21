import pytest


class _FakeResp:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}


class _FakeClient:
    def __init__(self, captured: dict):
        self._captured = captured

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers=None, json=None):
        self._captured["url"] = url
        self._captured["headers"] = headers
        self._captured["json"] = json
        return _FakeResp()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("adapter_name", "base_env", "base_url", "expected_suffix"),
    [
        ("NovitaAdapter", "NOVITA_BASE_URL", "https://api.novita.ai/openai", "/openai/v1/chat/completions"),
        ("PoeAdapter", "POE_BASE_URL", "https://api.poe.com/v1", "/v1/chat/completions"),
        ("TogetherAdapter", "TOGETHER_BASE_URL", "https://api.together.xyz/v1", "/v1/chat/completions"),
    ],
)
def test_openai_compatible_provider_adapter_url_resolution(
    monkeypatch,
    adapter_name: str,
    base_env: str,
    base_url: str,
    expected_suffix: str,
):
    from tldw_Server_API.app.core.LLM_Calls.providers import custom_openai_adapter as adapter_module

    monkeypatch.setenv(base_env, base_url)
    captured = {}
    monkeypatch.setattr(
        adapter_module,
        "http_client_factory",
        lambda *args, **kwargs: _FakeClient(captured),
    )

    adapter_cls = getattr(adapter_module, adapter_name)
    adapter = adapter_cls()

    result = adapter.chat(
        {
            "messages": [{"role": "user", "content": "hello"}],
            "model": "test-model",
            "api_key": "sk-test",
        }
    )

    assert result["choices"][0]["message"]["content"] == "ok"
    assert captured["url"].endswith(expected_suffix)
    assert captured["json"]["model"] == "test-model"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
