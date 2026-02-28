import configparser

import pytest


class _FakeTokenizer:
    def __init__(self, name: str = "o200k_base") -> None:
        self.name = name

    def encode(self, text: str, disallowed_special=()):  # noqa: ARG002 - compat signature
        return [ord(ch) for ch in text]

    def decode(self, token_ids):
        return "".join(chr(int(token_id)) for token_id in token_ids)


def test_resolve_tokenizer_openrouter_openai_canonical_exact(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    monkeypatch.setattr(resolver, "resolve_tiktoken_encoding", lambda model: _FakeTokenizer("o200k_base"))

    resolution = resolver.resolve_tokenizer(
        "openrouter",
        "openai/gpt-4o-mini",
        strict_mode_effective=True,
    )

    assert resolution.available is True
    assert resolution.count_accuracy == "exact"
    assert resolution.tokenizer == "tiktoken:o200k_base"
    assert resolution.kind == "tiktoken"
    assert resolution.strict_mode_effective is True


def test_resolve_tokenizer_non_exact_best_effort_classified_unavailable(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    monkeypatch.setattr(resolver, "resolve_tiktoken_encoding", lambda model: _FakeTokenizer("cl100k_base"))

    resolution = resolver.resolve_tokenizer(
        "deepseek",
        "gpt-3.5-turbo",
        strict_mode_effective=True,
    )

    assert resolution.available is True
    assert resolution.count_accuracy == "unavailable"
    assert resolution.tokenizer == "tiktoken:cl100k_base"
    assert resolution.kind == "tiktoken"


def test_resolve_tokenizer_openai_unavailable_error_not_masked_by_native_config(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    def _raise_unavailable(_model: str):
        raise resolver.TokenizerUnavailable("Tokenizer not available for provider/model")

    monkeypatch.setattr(resolver, "resolve_tiktoken_encoding", _raise_unavailable)

    resolution = resolver.resolve_tokenizer(
        "openai",
        "definitely-not-a-real-model",
        strict_mode_effective=False,
    )

    assert resolution.available is False
    assert "not available" in str(resolution.error or "").lower()
    assert "provider-native tokenizer is not configured for provider" not in str(resolution.error or "").lower()


def test_resolve_tokenizer_anthropic_count_only_exact_from_config():
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    config = configparser.ConfigParser()
    config.add_section("API")
    config.set("API", "anthropic_api_key", "anthropic-test-key")

    resolution = resolver.resolve_tokenizer(
        "anthropic",
        "claude-opus-4-20250514",
        strict_mode_effective=True,
        config_parser=config,
    )

    assert resolution.available is True
    assert resolution.count_accuracy == "exact"
    assert resolution.kind == "provider-native-count"
    assert resolution.source == "anthropic.http.count_tokens"
    assert resolution.tokenizer == "anthropic:remote-count"
    assert resolution.detokenize_available is False
    assert callable(getattr(resolution.encoding, "count_tokens", None))


def test_resolve_tokenizer_google_count_only_exact_from_config():
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    config = configparser.ConfigParser()
    config.add_section("API")
    config.set("API", "google_api_key", "google-test-key")

    resolution = resolver.resolve_tokenizer(
        "google",
        "gemini-2.5-flash",
        strict_mode_effective=True,
        config_parser=config,
    )

    assert resolution.available is True
    assert resolution.count_accuracy == "exact"
    assert resolution.kind == "provider-native-count"
    assert resolution.source == "google.http.count_tokens"
    assert resolution.tokenizer == "google:remote-count"
    assert resolution.detokenize_available is False
    assert callable(getattr(resolution.encoding, "count_tokens", None))


def test_resolve_tokenizer_cohere_tokenizer_exact_from_config():
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    config = configparser.ConfigParser()
    config.add_section("API")
    config.set("API", "cohere_api_key", "cohere-test-key")

    resolution = resolver.resolve_tokenizer(
        "cohere",
        "command-a-03-2025",
        strict_mode_effective=True,
        config_parser=config,
    )

    assert resolution.available is True
    assert resolution.count_accuracy == "exact"
    assert resolution.kind == "provider-native"
    assert resolution.source == "cohere.http.tokenize"
    assert resolution.tokenizer == "cohere:remote"
    assert resolution.detokenize_available is True
    assert callable(getattr(resolution.encoding, "encode", None))
    assert callable(getattr(resolution.encoding, "decode", None))


def test_resolve_tokenizer_bedrock_anthropic_count_only_exact_from_config():
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    config = configparser.ConfigParser()
    config.add_section("API")
    config.set("API", "bedrock_api_key", "bedrock-test-key")
    config.set("API", "bedrock_model", "anthropic.claude-3-5-sonnet-20240620-v1:0")

    resolution = resolver.resolve_tokenizer(
        "bedrock",
        "anthropic.claude-3-5-sonnet-20240620-v1:0",
        strict_mode_effective=True,
        config_parser=config,
    )

    assert resolution.available is True
    assert resolution.count_accuracy == "exact"
    assert resolution.kind == "provider-native-count"
    assert resolution.source == "bedrock.http.count_tokens"
    assert resolution.tokenizer == "bedrock:remote-count"
    assert resolution.detokenize_available is False
    assert callable(getattr(resolution.encoding, "count_tokens", None))


def test_resolve_tokenizer_bedrock_non_anthropic_not_exact(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    monkeypatch.setattr(resolver, "resolve_tiktoken_encoding", lambda _model: _FakeTokenizer("cl100k_base"))

    config = configparser.ConfigParser()
    config.add_section("API")
    config.set("API", "bedrock_api_key", "bedrock-test-key")

    resolution = resolver.resolve_tokenizer(
        "bedrock",
        "openai.gpt-oss-20b-1:0",
        strict_mode_effective=True,
        config_parser=config,
    )

    assert resolution.available is True
    assert resolution.count_accuracy == "unavailable"
    assert resolution.kind == "tiktoken"
    assert resolution.tokenizer == "tiktoken:cl100k_base"


def test_bedrock_count_only_adapter_calls_runtime_count_tokens(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    calls: list[tuple[str, dict[str, str], dict[str, object]]] = []

    class _FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict[str, object]:
            return self._payload

    def _fake_post(*, url: str, payload, headers, timeout):  # noqa: ANN001, ARG001
        calls.append((url, dict(headers), dict(payload)))
        return _FakeResponse(200, {"inputTokens": 9})

    monkeypatch.setattr(resolver, "_http_post", _fake_post)

    adapter = resolver.BedrockCountOnlyHTTPAdapter(
        base_url="https://bedrock-runtime.us-west-2.amazonaws.com",
        model="anthropic.claude-3-5-sonnet-20240620-v1:0",
        api_key="bedrock-test-key",
    )

    count = adapter.count_tokens("hello")
    assert count == 9
    assert calls
    assert "/model/anthropic.claude-3-5-sonnet-20240620-v1%3A0/count-tokens" in calls[0][0]
    assert calls[0][1].get("Authorization") == "Bearer bedrock-test-key"


def test_resolve_tokenizer_ollama_native_exact_from_config():
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    config = configparser.ConfigParser()
    config.add_section("Local-API")
    config.set("Local-API", "ollama_api_IP", "http://127.0.0.1:11434/api/chat")

    resolution = resolver.resolve_tokenizer(
        "ollama",
        "llama3.2",
        strict_mode_effective=True,
        config_parser=config,
    )

    assert resolution.available is True
    assert resolution.count_accuracy == "exact"
    assert resolution.kind == "provider-native"
    assert resolution.source == "ollama.http.tokenize"
    assert resolution.tokenizer == "ollama:remote"


def test_resolve_tokenizer_mlx_prefers_active_registry(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    active = _FakeTokenizer("mlx-active")

    monkeypatch.setattr(resolver, "_get_active_mlx_tokenizer", lambda _model: (active, "active-model"))
    monkeypatch.setattr(
        resolver,
        "_load_mlx_artifact_tokenizer",
        lambda _model: pytest.fail("artifact fallback should not run when registry tokenizer is active"),
    )

    resolution = resolver.resolve_tokenizer("mlx", "active-model", strict_mode_effective=True)

    assert resolution.available is True
    assert resolution.count_accuracy == "exact"
    assert resolution.kind == "provider-native"
    assert resolution.source == "mlx.registry.active"
    assert resolution.tokenizer == "mlx:active:active-model"


def test_resolve_tokenizer_mlx_uses_artifact_fallback(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    monkeypatch.setattr(resolver, "_get_active_mlx_tokenizer", lambda _model: None)
    monkeypatch.setattr(resolver, "_load_mlx_artifact_tokenizer", lambda _model: _FakeTokenizer("mlx-artifact"))

    resolution = resolver.resolve_tokenizer("mlx", "/tmp/fake-mlx-model", strict_mode_effective=True)

    assert resolution.available is True
    assert resolution.count_accuracy == "exact"
    assert resolution.kind == "provider-native"
    assert resolution.source == "mlx.artifact.tokenizer"
    assert resolution.tokenizer == "mlx:artifact"


def test_resolve_tokenizer_metadata_contains_strict_fields(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    monkeypatch.setattr(resolver, "resolve_tiktoken_encoding", lambda model: _FakeTokenizer("cl100k_base"))

    metadata = resolver.resolve_tokenizer_metadata(
        "openai",
        "gpt-4o-mini",
        strict_mode_effective=False,
    )

    assert metadata["available"] is True
    assert metadata["count_accuracy"] == "exact"
    assert metadata["strict_mode_effective"] is False
    assert metadata["tokenizer"] == "tiktoken:cl100k_base"


def test_google_count_only_adapter_falls_back_to_query_key_auth(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    calls: list[tuple[str, dict[str, str]]] = []

    class _FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict[str, object]:
            return self._payload

    def _fake_post(*, url: str, payload, headers, timeout):  # noqa: ANN001, ARG001
        calls.append((url, dict(headers)))
        if "?key=test-google-key" in url:
            return _FakeResponse(200, {"totalTokens": 7})
        return _FakeResponse(401, {"error": {"message": "invalid key transport"}})

    monkeypatch.setattr(resolver, "_http_post", _fake_post)

    adapter = resolver.GoogleCountOnlyHTTPAdapter(
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model="gemini-2.5-flash",
        api_key="test-google-key",
    )

    count = adapter.count_tokens("hello world")
    assert count == 7
    assert any("?key=test-google-key" in url for url, _headers in calls)
    assert any(headers.get("x-goog-api-key") == "test-google-key" for _url, headers in calls)


def test_coerce_int_rejects_non_integral_float():
    from tldw_Server_API.app.core.LLM_Calls import tokenizer_resolver as resolver

    assert resolver._coerce_int(12.5) is None
    assert resolver._coerce_int(12.0) == 12
