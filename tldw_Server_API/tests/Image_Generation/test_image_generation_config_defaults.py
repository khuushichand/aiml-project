from tldw_Server_API.app.core.Image_Generation import config as image_config


def test_image_generation_config_sane_defaults(monkeypatch):
    monkeypatch.setattr(image_config, "get_config_section", lambda *_args, **_kwargs: {})
    image_config.reset_image_generation_config_cache()

    cfg = image_config.get_image_generation_config(reload=True)

    assert cfg.default_backend == image_config.DEFAULT_BACKEND
    assert cfg.enabled_backends == []
    assert cfg.swarmui_base_url == image_config.DEFAULT_SWARMUI_BASE_URL
    assert cfg.openrouter_image_base_url == image_config.DEFAULT_OPENROUTER_IMAGE_BASE_URL
    assert cfg.openrouter_image_default_model == image_config.DEFAULT_OPENROUTER_IMAGE_MODEL
    assert cfg.novita_image_base_url == image_config.DEFAULT_NOVITA_IMAGE_BASE_URL
    assert cfg.novita_image_default_model == image_config.DEFAULT_NOVITA_IMAGE_MODEL
    assert cfg.together_image_base_url == image_config.DEFAULT_TOGETHER_IMAGE_BASE_URL
    assert cfg.together_image_default_model == image_config.DEFAULT_TOGETHER_IMAGE_MODEL

    
def test_image_generation_config_modelstudio_defaults(monkeypatch):
    monkeypatch.setattr(image_config, "get_config_section", lambda *_args, **_kwargs: {})
    image_config.reset_image_generation_config_cache()

    cfg = image_config.get_image_generation_config(reload=True)

    assert cfg.modelstudio_image_base_url is None

    assert cfg.modelstudio_image_base_url == image_config.DEFAULT_MODELSTUDIO_IMAGE_BASE_URL
    assert cfg.modelstudio_image_default_model == image_config.DEFAULT_MODELSTUDIO_IMAGE_MODEL
    assert cfg.modelstudio_image_region == image_config.DEFAULT_MODELSTUDIO_IMAGE_REGION
    assert cfg.modelstudio_image_mode == image_config.DEFAULT_MODELSTUDIO_IMAGE_MODE
