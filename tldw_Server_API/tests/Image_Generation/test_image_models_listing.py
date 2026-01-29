from pathlib import Path

from tldw_Server_API.app.core.Image_Generation.config import ImageGenerationConfig
from tldw_Server_API.app.core.Image_Generation import listing


class _FakeAdapter:
    supported_formats = {"png", "jpg", "webp"}


class _FakeRegistry:
    def __init__(self, names):
        self._names = list(names)

    def list_backend_names(self, *, include_disabled: bool = False):
        return list(self._names)

    def get_adapter_class(self, name):
        if name in self._names:
            return _FakeAdapter
        return None


def _make_config(**overrides) -> ImageGenerationConfig:
    base = dict(
        default_backend="stable_diffusion_cpp",
        enabled_backends=["stable_diffusion_cpp"],
        max_width=1024,
        max_height=1024,
        max_pixels=1024 * 1024,
        max_steps=50,
        max_prompt_length=1000,
        inline_max_bytes=4000000,
        sd_cpp_diffusion_model_path=None,
        sd_cpp_llm_path=None,
        sd_cpp_binary_path=None,
        sd_cpp_model_path=None,
        sd_cpp_vae_path=None,
        sd_cpp_lora_paths=[],
        sd_cpp_allowed_extra_params=[],
        sd_cpp_default_steps=25,
        sd_cpp_default_cfg_scale=7.5,
        sd_cpp_default_sampler="euler_a",
        sd_cpp_device="auto",
        sd_cpp_timeout_seconds=120,
        swarmui_base_url=None,
        swarmui_default_model=None,
        swarmui_swarm_token=None,
        swarmui_allowed_extra_params=[],
        swarmui_timeout_seconds=120,
    )
    base.update(overrides)
    return ImageGenerationConfig(**base)


def _touch(path: Path) -> Path:
    path.write_text("x", encoding="utf-8")
    return path


def test_list_image_models_configured(monkeypatch, tmp_path):
    binary = _touch(tmp_path / "sd-cli")
    model = _touch(tmp_path / "model.gguf")
    cfg = _make_config(sd_cpp_binary_path=str(binary), sd_cpp_model_path=str(model))

    monkeypatch.setattr(listing, "get_image_generation_config", lambda: cfg)
    monkeypatch.setattr(listing, "get_registry", lambda: _FakeRegistry(["stable_diffusion_cpp"]))

    models = listing.list_image_models_for_catalog()
    assert len(models) == 1
    entry = models[0]
    assert entry["id"] == "image/stable_diffusion_cpp"
    assert entry["type"] == "image"
    assert entry["is_configured"] is True
    assert "supported_formats" in entry
    assert "png" in entry["supported_formats"]


def test_list_image_models_unconfigured_missing_model(monkeypatch, tmp_path):
    binary = _touch(tmp_path / "sd-cli")
    cfg = _make_config(sd_cpp_binary_path=str(binary))

    monkeypatch.setattr(listing, "get_image_generation_config", lambda: cfg)
    monkeypatch.setattr(listing, "get_registry", lambda: _FakeRegistry(["stable_diffusion_cpp"]))

    models = listing.list_image_models_for_catalog()
    assert len(models) == 1
    entry = models[0]
    assert entry["is_configured"] is False


def test_list_image_models_swarmui_configured(monkeypatch):
    cfg = _make_config(enabled_backends=["swarmui"], swarmui_base_url="http://localhost:7801")

    monkeypatch.setattr(listing, "get_image_generation_config", lambda: cfg)
    monkeypatch.setattr(listing, "get_registry", lambda: _FakeRegistry(["swarmui"]))

    models = listing.list_image_models_for_catalog()
    assert len(models) == 1
    entry = models[0]
    assert entry["id"] == "image/swarmui"
    assert entry["is_configured"] is True


def test_list_image_models_swarmui_unconfigured(monkeypatch):
    cfg = _make_config(enabled_backends=["swarmui"], swarmui_base_url=None)

    monkeypatch.setattr(listing, "get_image_generation_config", lambda: cfg)
    monkeypatch.setattr(listing, "get_registry", lambda: _FakeRegistry(["swarmui"]))

    models = listing.list_image_models_for_catalog()
    assert len(models) == 1
    entry = models[0]
    assert entry["is_configured"] is False
