from tldw_Server_API.app.core.AuthNZ.llm_provider_overrides import (
    LLMProviderOverride,
    apply_llm_provider_overrides_to_listing,
    get_override_model_priority,
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


def test_get_override_model_priority_reads_routing_rankings() -> None:
    set_llm_provider_overrides_cache_for_tests(
        {
            "openai": LLMProviderOverride(
                provider="openai",
                config={
                    "routing": {
                        "model_rankings": {
                            "highest_quality": ["gpt-4.1", "gpt-4.1-mini"],
                        }
                    }
                },
            )
        }
    )

    assert get_override_model_priority("openai", "highest_quality") == [
        "gpt-4.1",
        "gpt-4.1-mini",
    ]

    updated = apply_llm_provider_overrides_to_listing(
        {
            "providers": [
                {
                    "name": "openai",
                    "models": ["gpt-4.1-mini", "gpt-4.1"],
                    "models_info": [
                        {"name": "gpt-4.1-mini"},
                        {"name": "gpt-4.1"},
                    ],
                }
            ]
        }
    )
    assert updated["providers"][0]["models"] == ["gpt-4.1", "gpt-4.1-mini"]
    assert [
        model["name"] for model in updated["providers"][0]["models_info"]
    ] == ["gpt-4.1", "gpt-4.1-mini"]

    set_llm_provider_overrides_cache_for_tests({})


def test_apply_overrides_sorts_models_info_without_crashing_on_non_dict_entries() -> None:
    set_llm_provider_overrides_cache_for_tests(
        {
            "openai": LLMProviderOverride(
                provider="openai",
                config={
                    "routing": {
                        "model_rankings": {
                            "highest_quality": ["gpt-4.1", "gpt-4.1-mini"],
                        }
                    }
                },
            )
        }
    )

    updated = apply_llm_provider_overrides_to_listing(
        {
            "providers": [
                {
                    "name": "openai",
                    "models_info": [
                        None,
                        {"name": "gpt-4.1-mini"},
                        "broken",
                        {"name": "gpt-4.1"},
                    ],
                }
            ]
        }
    )

    assert [
        model["name"] for model in updated["providers"][0]["models_info"]
    ] == ["gpt-4.1", "gpt-4.1-mini"]

    set_llm_provider_overrides_cache_for_tests({})
