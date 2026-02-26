from tldw_Server_API.app.core.LLM_Calls.extra_body_compat_catalog import (
    get_model_extra_body_compat,
    get_provider_extra_body_compat,
)


def test_known_provider_returns_supported_shape():
    data = get_provider_extra_body_compat("openai")
    assert isinstance(data["known_params"], list)
    assert "source" in data


def test_model_level_shape_present():
    data = get_model_extra_body_compat("openai", "gpt-4o-mini")
    assert isinstance(data["known_params"], list)
    assert "effective_reason" in data


def test_runtime_strict_context_disables_nonstandard_support():
    data = get_model_extra_body_compat(
        "openai",
        "gpt-4o-mini",
        runtime_context={"strict_openai_compat": True},
    )
    assert data["supported"] is False


def test_unknown_provider_returns_safe_fallback():
    data = get_provider_extra_body_compat("definitely-unknown-provider")
    assert data["supported"] is False
    assert data["known_params"] == []
    assert data["example"] == {"extra_body": {}}
