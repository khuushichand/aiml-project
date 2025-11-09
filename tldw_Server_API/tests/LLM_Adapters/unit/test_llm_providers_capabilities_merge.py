import configparser
import pytest


def _fake_config():
    cfg = configparser.ConfigParser()
    cfg.add_section("API")
    cfg.set("API", "openai_api_key", "sk-test")
    cfg.set("API", "openai_model", "gpt-4o-mini")
    cfg.set("API", "default_api", "openai")
    # Provide minimal Local-API section to satisfy callers that probe both
    cfg.add_section("Local-API")
    return cfg


def test_llm_providers_merges_adapter_capabilities(monkeypatch, client_user_only):
    # Force adapters available even though this is not strictly required for the endpoint
    monkeypatch.setenv("LLM_ADAPTERS_ENABLED", "1")

    # Stub configuration loader to return a controlled config
    import tldw_Server_API.app.core.config as core_config
    monkeypatch.setattr(core_config, "load_comprehensive_config", _fake_config)

    # Stub registry capability discovery
    import tldw_Server_API.app.core.LLM_Calls.adapter_registry as reg_mod

    class _DummyReg:
        def get_all_capabilities(self):
            return {"openai": {"json_mode": True, "supports_tools": True, "extra_cap": "adapter"}}

    monkeypatch.setattr(reg_mod, "get_registry", lambda: _DummyReg())

    client = client_user_only
    r = client.get("/api/v1/llm/providers")
    assert r.status_code == 200
    data = r.json()
    providers = {p["name"]: p for p in data.get("providers", [])}
    assert "openai" in providers
    caps = providers["openai"].get("capabilities", {})
    # Adapter-provided fields should be present
    assert caps.get("json_mode") is True
    assert caps.get("supports_tools") is True
    assert caps.get("extra_cap") == "adapter"
