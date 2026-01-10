from tldw_Server_API.app.core.AuthNZ.llm_provider_overrides import (
    LLMProviderOverride,
    apply_llm_provider_overrides_to_listing,
    set_llm_provider_overrides_cache_for_tests,
    validate_provider_override,
)


def test_apply_overrides_filters_models_and_status() -> None:
    set_llm_provider_overrides_cache_for_tests(
        {
            "openai": LLMProviderOverride(
                provider="openai",
                is_enabled=False,
                allowed_models=["gpt-4o"],
                api_key_hint="abcd",
            )
        }
    )

    payload = {
        "providers": [
            {
                "name": "openai",
                "enabled": True,
                "models": ["gpt-4o", "gpt-3.5-turbo"],
                "models_info": [
                    {"name": "gpt-4o", "notes": "ok"},
                    {"name": "gpt-3.5-turbo", "notes": "legacy"},
                ],
            }
        ]
    }

    updated = apply_llm_provider_overrides_to_listing(payload)
    provider = updated["providers"][0]
    assert provider["enabled"] is False
    assert provider["models"] == ["gpt-4o"]
    assert provider["models_info"] == [{"name": "gpt-4o", "notes": "ok"}]

    set_llm_provider_overrides_cache_for_tests({})


def test_validate_provider_override_blocks_disallowed_model() -> None:
    set_llm_provider_overrides_cache_for_tests(
        {
            "openai": LLMProviderOverride(
                provider="openai",
                is_enabled=True,
                allowed_models=["gpt-4o"],
            )
        }
    )

    blocked = validate_provider_override("openai", "gpt-3.5-turbo")
    assert blocked is not None
    assert blocked["error_code"] == "model_not_allowed"

    allowed = validate_provider_override("openai", "gpt-4o")
    assert allowed is None

    set_llm_provider_overrides_cache_for_tests({})
