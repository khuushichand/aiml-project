from types import SimpleNamespace

from tldw_Server_API.app.core.File_Artifacts.adapters.image_adapter import ImageAdapter


def test_modelstudio_allowlist_uses_config_field():
    cfg = SimpleNamespace(modelstudio_image_allowed_extra_params=["watermark", "seed_offset"])
    allowlist = ImageAdapter._allowed_extra_params("modelstudio", cfg)
    assert allowlist == {"watermark", "seed_offset"}
