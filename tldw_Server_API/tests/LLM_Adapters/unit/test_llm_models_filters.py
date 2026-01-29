import configparser


def _fake_config():
    cfg = configparser.ConfigParser()
    cfg.add_section("API")
    cfg.set("API", "openai_api_key", "sk-test")
    cfg.set("API", "openai_model", "gpt-4o-mini, text-embedding-3-small")
    cfg.set("API", "default_api", "openai")
    # Provide minimal Local-API section to satisfy callers that probe both
    cfg.add_section("Local-API")
    return cfg


def _patch_llm_providers(monkeypatch):
    import tldw_Server_API.app.api.v1.endpoints.llm_providers as llm_providers

    monkeypatch.setattr(llm_providers, "load_comprehensive_config", _fake_config)
    monkeypatch.setattr(llm_providers, "list_provider_models", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(llm_providers, "apply_llm_provider_overrides_to_listing", lambda result: result)
    monkeypatch.setattr(llm_providers, "get_api_keys", lambda: {})
    monkeypatch.setattr(llm_providers, "list_image_models_for_catalog", _fake_image_models)


def _fake_image_models():
    return [
        {
            "provider": "image",
            "id": "image/stable_diffusion_cpp",
            "name": "stable_diffusion_cpp",
            "type": "image",
            "capabilities": {"image_generation": True},
            "modalities": {"input": ["text"], "output": ["image"]},
            "is_configured": False,
            "supported_formats": ["png", "jpg", "webp"],
        }
    ]


def test_llm_models_filter_type(monkeypatch, client_user_only):
    _patch_llm_providers(monkeypatch)

    client = client_user_only
    r = client.get("/api/v1/llm/models?type=chat")
    assert r.status_code == 200
    data = r.json()
    assert "openai/gpt-4o-mini" in data
    assert "openai/text-embedding-3-small" not in data

    r = client.get("/api/v1/llm/models?type=embedding")
    assert r.status_code == 200
    data = r.json()
    assert "openai/text-embedding-3-small" in data
    assert "openai/gpt-4o-mini" not in data
    assert "image/stable_diffusion_cpp" not in data

    r = client.get("/api/v1/llm/models?type=image")
    assert r.status_code == 200
    data = r.json()
    assert "image/stable_diffusion_cpp" in data


def test_llm_models_metadata_filter_modalities(monkeypatch, client_user_only):
    _patch_llm_providers(monkeypatch)

    client = client_user_only
    r = client.get("/api/v1/llm/models/metadata?input_modality=image")
    assert r.status_code == 200
    payload = r.json()
    names = {m.get("name") for m in payload.get("models", [])}
    assert "gpt-4o-mini" in names
    assert "text-embedding-3-small" not in names
    assert "stable_diffusion_cpp" not in names

    r = client.get("/api/v1/llm/models/metadata?output_modality=image")
    assert r.status_code == 200
    payload = r.json()
    names = {m.get("name") for m in payload.get("models", [])}
    assert "stable_diffusion_cpp" in names
    assert "gpt-4o-mini" not in names
