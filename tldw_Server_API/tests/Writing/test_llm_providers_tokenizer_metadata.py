import configparser


def _fake_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.add_section("API")
    cfg.set("API", "openai_api_key", "sk-test")
    cfg.set("API", "openai_model", "gpt-4o-mini")
    cfg.set("API", "anthropic_api_key", "anthropic-test-key")
    cfg.set("API", "anthropic_model", "claude-opus-4-20250514")
    cfg.set("API", "google_api_key", "google-test-key")
    cfg.set("API", "google_model", "gemini-2.5-flash")
    cfg.set("API", "groq_api_key", "groq-test-key")
    cfg.set("API", "groq_model", "openai/gpt-4o-mini")
    cfg.set("API", "cohere_api_key", "cohere-test-key")
    cfg.set("API", "cohere_model", "command-a-03-2025")
    cfg.set("API", "deepseek_api_key", "deepseek-test-key")
    cfg.set("API", "deepseek_model", "deepseek-chat")
    cfg.set("API", "mistral_api_key", "mistral-test-key")
    cfg.set("API", "mistral_model", "mistral-large-latest")
    cfg.set("API", "bedrock_api_key", "bedrock-test-key")
    cfg.set("API", "bedrock_model", "anthropic.claude-3-5-sonnet-20240620-v1:0")
    cfg.set("API", "bedrock_region", "us-west-2")
    cfg.set("API", "default_api", "openai")

    cfg.add_section("Local-API")
    cfg.set("Local-API", "ollama_api_IP", "http://127.0.0.1:11434")
    cfg.set("Local-API", "ollama_model", "llama3.2")

    cfg.add_section("MLX")
    cfg.set("MLX", "mlx_model_path", "/tmp/mlx-model")
    return cfg


def test_llm_providers_tokenizer_metadata_mirrors_strict_fields(monkeypatch):
    import tldw_Server_API.app.api.v1.endpoints.llm_providers as llm_endpoints

    monkeypatch.setattr(llm_endpoints, "load_comprehensive_config", _fake_config)
    monkeypatch.setattr(llm_endpoints, "list_provider_models", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(llm_endpoints, "apply_llm_provider_overrides_to_listing", lambda result: result)
    monkeypatch.setattr(llm_endpoints, "get_api_keys", lambda: {})
    monkeypatch.setattr(llm_endpoints, "list_image_models_for_catalog", lambda: [])
    monkeypatch.setattr(llm_endpoints, "_llm_registry_capability_envelopes", lambda: {})

    def _fake_tokenizer_metadata(provider, model, **_kwargs):
        key = (provider.strip().lower(), model.strip())
        if key[0] in {"ollama", "mlx"}:
            return {
                "available": True,
                "tokenizer": f"{key[0]}:remote",
                "kind": "provider-native",
                "source": f"{key[0]}.http.tokenize",
                "detokenize": True,
                "count_accuracy": "exact",
                "strict_mode_effective": False,
            }
        return {
            "available": False,
            "tokenizer": None,
            "kind": None,
            "source": None,
            "detokenize": False,
            "count_accuracy": "unavailable",
            "strict_mode_effective": False,
            "error": "Tokenizer not available",
        }

    monkeypatch.setattr(llm_endpoints, "resolve_tokenizer_metadata", _fake_tokenizer_metadata)

    payload = llm_endpoints.get_configured_providers(include_deprecated=False)
    providers = {p["name"]: p for p in payload["providers"]}

    assert "ollama" in providers
    assert "mlx" in providers

    ollama_model = providers["ollama"]["models"][0]
    ollama_tokenizer = providers["ollama"]["tokenizers"][ollama_model]
    assert ollama_tokenizer["count_accuracy"] == "exact"
    assert ollama_tokenizer["strict_mode_effective"] is False

    mlx_model = providers["mlx"]["models"][0]
    mlx_tokenizer = providers["mlx"]["tokenizers"][mlx_model]
    assert mlx_tokenizer["count_accuracy"] == "exact"
    assert mlx_tokenizer["strict_mode_effective"] is False

    for model_info in providers["openai"]["models_info"]:
        assert "count_accuracy" in model_info
        assert "strict_mode_effective" in model_info


def test_llm_providers_tokenizer_metadata_reflects_strict_runtime_env(monkeypatch):
    import tldw_Server_API.app.api.v1.endpoints.llm_providers as llm_endpoints

    monkeypatch.setenv("STRICT_TOKEN_COUNTING", "true")
    monkeypatch.setattr(llm_endpoints, "load_comprehensive_config", _fake_config)
    monkeypatch.setattr(llm_endpoints, "list_provider_models", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(llm_endpoints, "apply_llm_provider_overrides_to_listing", lambda result: result)
    monkeypatch.setattr(llm_endpoints, "get_api_keys", lambda: {})
    monkeypatch.setattr(llm_endpoints, "list_image_models_for_catalog", lambda: [])
    monkeypatch.setattr(llm_endpoints, "_llm_registry_capability_envelopes", lambda: {})

    def _fake_tokenizer_metadata(provider, model, **kwargs):  # noqa: ARG001
        strict_effective = bool(kwargs.get("strict_mode_effective"))
        return {
            "available": True,
            "tokenizer": "fake:strict",
            "kind": "provider-native",
            "source": "fake.strict",
            "detokenize": True,
            "count_accuracy": "exact",
            "strict_mode_effective": strict_effective,
        }

    monkeypatch.setattr(llm_endpoints, "resolve_tokenizer_metadata", _fake_tokenizer_metadata)

    payload = llm_endpoints.get_configured_providers(include_deprecated=False)
    providers = {p["name"]: p for p in payload["providers"]}

    ollama_model = providers["ollama"]["models"][0]
    mlx_model = providers["mlx"]["models"][0]
    openai_model = providers["openai"]["models"][0]

    assert providers["ollama"]["tokenizers"][ollama_model]["strict_mode_effective"] is True
    assert providers["mlx"]["tokenizers"][mlx_model]["strict_mode_effective"] is True
    assert providers["openai"]["tokenizers"][openai_model]["strict_mode_effective"] is True

    for model_info in providers["openai"]["models_info"]:
        assert model_info["strict_mode_effective"] is True


def test_llm_providers_real_resolver_exact_for_anthropic_google_cohere_bedrock_groq(monkeypatch):
    import tldw_Server_API.app.api.v1.endpoints.llm_providers as llm_endpoints
    import tldw_Server_API.app.core.LLM_Calls.tokenizer_resolver as resolver_module
    from tldw_Server_API.app.core.LLM_Calls.tokenizer_resolver import (
        resolve_tokenizer_metadata as resolve_tokenizer_metadata_shared,
    )

    monkeypatch.delenv("STRICT_TOKEN_COUNTING", raising=False)
    monkeypatch.setattr(llm_endpoints, "load_comprehensive_config", _fake_config)
    monkeypatch.setattr(llm_endpoints, "list_provider_models", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(llm_endpoints, "apply_llm_provider_overrides_to_listing", lambda result: result)
    monkeypatch.setattr(llm_endpoints, "get_api_keys", lambda: {})
    monkeypatch.setattr(llm_endpoints, "list_image_models_for_catalog", lambda: [])
    monkeypatch.setattr(llm_endpoints, "_llm_registry_capability_envelopes", lambda: {})

    class _FakeTokenizer:
        name = "o200k_base"

        def encode(self, text: str, disallowed_special=()):  # noqa: ARG002
            return [ord(ch) for ch in text]

        def decode(self, token_ids):
            return "".join(chr(int(token_id)) for token_id in token_ids)

    monkeypatch.setattr(resolver_module, "resolve_tiktoken_encoding", lambda _model: _FakeTokenizer())

    # Avoid local env crashes from MLX artifact fallback importing transformers/torch in this test process.
    def _safe_resolve_metadata(provider, model, **kwargs):
        if str(provider).strip().lower() == "mlx":
            return {
                "available": False,
                "tokenizer": None,
                "kind": None,
                "source": None,
                "detokenize": False,
                "count_accuracy": "unavailable",
                "strict_mode_effective": bool(kwargs.get("strict_mode_effective", False)),
                "error": "MLX tokenizer unavailable in test process",
            }
        return resolve_tokenizer_metadata_shared(provider, model, **kwargs)

    monkeypatch.setattr(llm_endpoints, "resolve_tokenizer_metadata", _safe_resolve_metadata)

    payload = llm_endpoints.get_configured_providers(include_deprecated=False)
    providers = {p["name"]: p for p in payload["providers"]}

    anthropic_model = providers["anthropic"]["models"][0]
    anthropic_tok = providers["anthropic"]["tokenizers"][anthropic_model]
    assert anthropic_tok["count_accuracy"] == "exact"
    assert anthropic_tok["kind"] == "provider-native-count"
    assert anthropic_tok["detokenize"] is False

    google_model = providers["google"]["models"][0]
    google_tok = providers["google"]["tokenizers"][google_model]
    assert google_tok["count_accuracy"] == "exact"
    assert google_tok["kind"] == "provider-native-count"
    assert google_tok["detokenize"] is False

    cohere_model = providers["cohere"]["models"][0]
    cohere_tok = providers["cohere"]["tokenizers"][cohere_model]
    assert cohere_tok["count_accuracy"] == "exact"
    assert cohere_tok["kind"] == "provider-native"
    assert cohere_tok["detokenize"] is True

    bedrock_model = providers["bedrock"]["models"][0]
    bedrock_tok = providers["bedrock"]["tokenizers"][bedrock_model]
    assert bedrock_tok["count_accuracy"] == "exact"
    assert bedrock_tok["kind"] == "provider-native-count"
    assert bedrock_tok["detokenize"] is False

    groq_model = providers["groq"]["models"][0]
    groq_tok = providers["groq"]["tokenizers"][groq_model]
    assert groq_tok["count_accuracy"] == "exact"
    assert groq_tok["kind"] == "tiktoken"
    assert groq_tok["detokenize"] is True

    deepseek_model = providers["deepseek"]["models"][0]
    deepseek_tok = providers["deepseek"]["tokenizers"][deepseek_model]
    assert deepseek_tok["count_accuracy"] == "unavailable"
    assert deepseek_tok["kind"] == "tiktoken"

    mistral_model = providers["mistral"]["models"][0]
    mistral_tok = providers["mistral"]["tokenizers"][mistral_model]
    assert mistral_tok["count_accuracy"] == "unavailable"
    assert mistral_tok["kind"] == "tiktoken"
