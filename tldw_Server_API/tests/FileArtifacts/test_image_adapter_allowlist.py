from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.File_Artifacts.adapters import image_adapter as image_adapter_module
from tldw_Server_API.app.core.File_Artifacts.adapters.image_adapter import ImageAdapter
from tldw_Server_API.app.core.Image_Generation.adapters.base import ImageGenResult
from tldw_Server_API.app.core.Image_Generation.capabilities import ResolvedReferenceImage


class _StubBackendAdapter:
    def __init__(self, result=None) -> None:
        self.result = result
        self.seen_requests = []

    def generate(self, request):
        self.seen_requests.append(request)
        if self.result is not None:
            return self.result
        return ImageGenResult(content=b"image", content_type="image/png", bytes_len=5)


class _StubRegistry:
    def __init__(self, adapter=None) -> None:
        self.adapter = adapter or _StubBackendAdapter()

    def resolve_backend(self, requested):
        return requested

    def get_adapter(self, name):
        return self.adapter


def test_modelstudio_allowlist_uses_config_field():
    cfg = SimpleNamespace(modelstudio_image_allowed_extra_params=["watermark", "seed_offset"])
    allowlist = ImageAdapter._allowed_extra_params("modelstudio", cfg)
    assert allowlist == {"watermark", "seed_offset"}


def test_modelstudio_mode_control_param_allowed_without_allowlist():
    cfg = SimpleNamespace(modelstudio_image_allowed_extra_params=[])
    adapter = ImageAdapter()
    issues = []
    adapter._validate_extra_params(  # noqa: SLF001 - direct unit test coverage
        {"backend": "modelstudio", "extra_params": {"mode": "async"}},
        cfg,
        issues,
    )
    assert issues == []


def test_modelstudio_mode_control_does_not_bypass_other_keys():
    cfg = SimpleNamespace(modelstudio_image_allowed_extra_params=[])
    adapter = ImageAdapter()
    issues = []
    adapter._validate_extra_params(  # noqa: SLF001 - direct unit test coverage
        {"backend": "modelstudio", "extra_params": {"mode": "async", "foo": "bar"}},
        cfg,
        issues,
    )
    assert len(issues) == 1
    assert issues[0].path == "extra_params.foo"


def test_image_adapter_normalize_preserves_reference_file_provenance(monkeypatch):
    cfg = SimpleNamespace(
        max_prompt_length=1000,
        sd_cpp_allowed_extra_params=[],
        swarmui_allowed_extra_params=[],
        openrouter_image_allowed_extra_params=[],
        novita_image_allowed_extra_params=[],
        together_image_allowed_extra_params=[],
        modelstudio_image_allowed_extra_params=[],
    )
    monkeypatch.setattr(image_adapter_module, "get_registry", lambda: _StubRegistry())
    monkeypatch.setattr(image_adapter_module, "get_image_generation_config", lambda: cfg)

    adapter = ImageAdapter()
    structured = adapter.normalize(
        {
            "backend": "modelstudio",
            "prompt": "draw a fox",
            "reference_file_id": "17",
        }
    )

    assert structured["reference_file_id"] == 17
    assert structured["reference_image_provenance"] == {
        "source": "managed_reference_image",
        "reference_file_id": 17,
    }
    assert "content" not in structured["reference_image_provenance"]
    assert "temp_path" not in structured["reference_image_provenance"]


def test_image_adapter_export_attaches_reference_image_when_supported(monkeypatch):
    cfg = SimpleNamespace(
        reference_image_supported_models={"modelstudio": ["qwen-image-edit"]},
        modelstudio_image_allowed_extra_params=[],
        sd_cpp_allowed_extra_params=[],
        swarmui_allowed_extra_params=[],
        openrouter_image_allowed_extra_params=[],
        novita_image_allowed_extra_params=[],
        together_image_allowed_extra_params=[],
    )
    backend = _StubBackendAdapter()
    monkeypatch.setattr(image_adapter_module, "get_registry", lambda: _StubRegistry(adapter=backend))
    monkeypatch.setattr(image_adapter_module, "get_image_generation_config", lambda: cfg)

    reference = ResolvedReferenceImage(
        file_id=17,
        filename="reference.png",
        mime_type="image/png",
        width=64,
        height=64,
        bytes_len=4,
        content=b"data",
        temp_path=None,
    )
    monkeypatch.setattr(
        image_adapter_module.ImageAdapter,
        "_resolve_reference_image",
        lambda self, structured, backend: reference,
    )

    token = image_adapter_module.set_image_adapter_request_context(collections_db=SimpleNamespace(), user_id=321)
    try:
        adapter = ImageAdapter()
        structured = {
            "backend": "modelstudio",
            "prompt": "draw a fox",
            "model": "qwen-image-edit-v1",
            "reference_file_id": 17,
            "reference_image_provenance": {"source": "managed_reference_image", "reference_file_id": 17},
            "extra_params": {},
        }
        result = adapter.export(
            structured,
            format="png",
        )
    finally:
        image_adapter_module.reset_image_adapter_request_context(token)

    assert result.content == b"image"
    assert backend.seen_requests
    assert backend.seen_requests[0].reference_image is reference
    assert structured["reference_image_provenance"]["snapshot"] == {
        "filename": "reference.png",
        "mime_type": "image/png",
        "width": 64,
        "height": 64,
    }


def test_image_adapter_export_rejects_unsupported_reference_image_backend(monkeypatch):
    cfg = SimpleNamespace(
        reference_image_supported_models={"modelstudio": ["qwen-image-edit"]},
        modelstudio_image_allowed_extra_params=[],
        sd_cpp_allowed_extra_params=[],
        swarmui_allowed_extra_params=[],
        openrouter_image_allowed_extra_params=[],
        novita_image_allowed_extra_params=[],
        together_image_allowed_extra_params=[],
    )
    monkeypatch.setattr(image_adapter_module, "get_registry", lambda: _StubRegistry())
    monkeypatch.setattr(image_adapter_module, "get_image_generation_config", lambda: cfg)

    adapter = ImageAdapter()

    with pytest.raises(
        image_adapter_module.FileArtifactsValidationError,
        match="reference_image_unsupported_by_backend",
    ):
        adapter.export(
            {
                "backend": "swarmui",
                "prompt": "draw a fox",
                "model": "any-model",
                "reference_file_id": 17,
                "reference_image_provenance": {"source": "managed_reference_image", "reference_file_id": 17},
                "extra_params": {},
            },
            format="png",
        )


def test_image_adapter_export_rejects_unsupported_reference_image_model(monkeypatch):
    cfg = SimpleNamespace(
        reference_image_supported_models={"modelstudio": ["qwen-image-edit"]},
        modelstudio_image_allowed_extra_params=[],
        sd_cpp_allowed_extra_params=[],
        swarmui_allowed_extra_params=[],
        openrouter_image_allowed_extra_params=[],
        novita_image_allowed_extra_params=[],
        together_image_allowed_extra_params=[],
    )
    monkeypatch.setattr(image_adapter_module, "get_registry", lambda: _StubRegistry())
    monkeypatch.setattr(image_adapter_module, "get_image_generation_config", lambda: cfg)

    adapter = ImageAdapter()

    with pytest.raises(
        image_adapter_module.FileArtifactsValidationError,
        match="reference_image_unsupported_by_model",
    ):
        adapter.export(
            {
                "backend": "modelstudio",
                "prompt": "draw a fox",
                "model": "other-model",
                "reference_file_id": 17,
                "reference_image_provenance": {"source": "managed_reference_image", "reference_file_id": 17},
                "extra_params": {},
            },
            format="png",
        )
