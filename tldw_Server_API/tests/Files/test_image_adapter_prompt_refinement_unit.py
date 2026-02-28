from dataclasses import replace

from tldw_Server_API.app.core.File_Artifacts.adapters import image_adapter as image_adapter_module
from tldw_Server_API.app.core.Image_Generation import config as image_config


class _StubRegistry:
    def resolve_backend(self, backend_name):
        candidate = (backend_name or "stable_diffusion_cpp").strip().lower()
        if candidate == "stable_diffusion_cpp":
            return "stable_diffusion_cpp"
        return None


def test_image_adapter_normalize_prompt_refinement_opt_in(monkeypatch):
    cfg = image_config.get_image_generation_config(reload=True)
    monkeypatch.setattr(image_adapter_module, "get_registry", lambda: _StubRegistry())
    monkeypatch.setattr(image_adapter_module, "get_image_generation_config", lambda: cfg)

    adapter = image_adapter_module.ImageAdapter()
    structured = adapter.normalize(
        {
            "backend": "stable_diffusion_cpp",
            "prompt": "cat portrait",
            "prompt_refinement": True,
        }
    )

    assert structured["prompt_refinement"] == "basic"
    assert structured["prompt"].startswith("cat portrait,")
    assert "high detail" in structured["prompt"]


def test_image_adapter_normalize_prompt_refinement_opt_out(monkeypatch):
    cfg = image_config.get_image_generation_config(reload=True)
    monkeypatch.setattr(image_adapter_module, "get_registry", lambda: _StubRegistry())
    monkeypatch.setattr(image_adapter_module, "get_image_generation_config", lambda: cfg)

    adapter = image_adapter_module.ImageAdapter()
    structured = adapter.normalize(
        {
            "backend": "stable_diffusion_cpp",
            "prompt": "cat portrait",
            "prompt_refinement": False,
        }
    )

    assert structured["prompt_refinement"] == "off"
    assert structured["prompt"] == "cat portrait"


def test_image_adapter_normalize_refinement_skips_when_max_length_exceeded(monkeypatch):
    cfg = replace(image_config.get_image_generation_config(reload=True), max_prompt_length=12)
    monkeypatch.setattr(image_adapter_module, "get_registry", lambda: _StubRegistry())
    monkeypatch.setattr(image_adapter_module, "get_image_generation_config", lambda: cfg)

    adapter = image_adapter_module.ImageAdapter()
    structured = adapter.normalize(
        {
            "backend": "stable_diffusion_cpp",
            "prompt": "cat portrait",
            "prompt_refinement": True,
        }
    )

    assert structured["prompt"] == "cat portrait"

