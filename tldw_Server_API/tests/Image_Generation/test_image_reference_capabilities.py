import pytest

from tldw_Server_API.app.core.Image_Generation.adapters.base import ImageGenRequest
from tldw_Server_API.app.core.Image_Generation import config as image_config
from tldw_Server_API.app.core.Image_Generation.capabilities import (
    ReferenceImageCapability,
    ResolvedReferenceImage,
    resolve_reference_image_capability,
)
from tldw_Server_API.app.core.Image_Generation.config import ImageGenerationConfig


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
        openrouter_image_base_url=None,
        openrouter_image_api_key=None,
        openrouter_image_default_model=None,
        openrouter_image_allowed_extra_params=[],
        openrouter_image_timeout_seconds=120,
        novita_image_base_url=None,
        novita_image_api_key=None,
        novita_image_default_model=None,
        novita_image_allowed_extra_params=[],
        novita_image_timeout_seconds=180,
        novita_image_poll_interval_seconds=2,
        together_image_base_url=None,
        together_image_api_key=None,
        together_image_default_model=None,
        together_image_allowed_extra_params=[],
        together_image_timeout_seconds=120,
        modelstudio_image_base_url=None,
        modelstudio_image_api_key=None,
        modelstudio_image_default_model="qwen-image",
        modelstudio_image_region="sg",
        modelstudio_image_mode="auto",
        modelstudio_image_poll_interval_seconds=2,
        modelstudio_image_timeout_seconds=180,
        modelstudio_image_allowed_extra_params=[],
    )
    base.update(overrides)
    return ImageGenerationConfig(**base)


def test_resolved_reference_image_allows_bytes_or_temp_path() -> None:
    reference = ResolvedReferenceImage(
        file_id=123,
        filename="source.png",
        mime_type="image/png",
        width=800,
        height=600,
        bytes_len=4,
        content=b"data",
        temp_path=None,
    )

    assert reference.content == b"data"
    assert reference.temp_path is None


def test_resolved_reference_image_rejects_missing_backing_representation() -> None:
    with pytest.raises(ValueError, match="exactly one of content or temp_path"):
        ResolvedReferenceImage(
            file_id=123,
            filename="source.png",
            mime_type="image/png",
            width=800,
            height=600,
            bytes_len=4,
            content=None,
            temp_path=None,
        )


def test_resolved_reference_image_rejects_both_backing_representations() -> None:
    with pytest.raises(ValueError, match="exactly one of content or temp_path"):
        ResolvedReferenceImage(
            file_id=123,
            filename="source.png",
            mime_type="image/png",
            width=800,
            height=600,
            bytes_len=4,
            content=b"data",
            temp_path="/tmp/source.png",
        )


def test_image_request_can_carry_resolved_reference_image() -> None:
    reference = ResolvedReferenceImage(
        file_id=123,
        filename="source.png",
        mime_type="image/png",
        width=800,
        height=600,
        bytes_len=4,
        content=None,
        temp_path="/tmp/source.png",
    )

    request = ImageGenRequest(
        backend="modelstudio",
        prompt="draw a cat",
        negative_prompt=None,
        width=1024,
        height=1024,
        steps=None,
        cfg_scale=None,
        seed=None,
        sampler=None,
        model="qwen-image",
        format="png",
        extra_params={},
        request_id=None,
        reference_image=reference,
    )

    assert request.reference_image is reference


def test_reference_capability_defaults_to_false_for_plain_qwen_image() -> None:
    capability = resolve_reference_image_capability("modelstudio", "qwen-image")

    assert capability == ReferenceImageCapability(supported=False, reason="unsupported_model")


@pytest.mark.parametrize("model", ["qwen-image-2.0", "qwen-image-2.0-turbo", "qwen-image-edit", "qwen-image-edit-v1"])
def test_reference_capability_supports_documented_model_families(model: str) -> None:
    capability = resolve_reference_image_capability("modelstudio", model)

    assert capability == ReferenceImageCapability(supported=True, reason=None)


def test_reference_capability_does_not_broaden_supported_models_with_config() -> None:
    cfg = _make_config(reference_image_supported_models={"modelstudio": ["foo-model"]})

    capability = resolve_reference_image_capability("modelstudio", "foo-model", config=cfg)

    assert capability == ReferenceImageCapability(supported=False, reason="unsupported_model")


def test_reference_capability_allows_config_to_narrow_builtin_support() -> None:
    cfg = _make_config(reference_image_supported_models={"modelstudio": []})

    capability = resolve_reference_image_capability("modelstudio", "qwen-image-edit-v1", config=cfg)

    assert capability == ReferenceImageCapability(supported=False, reason="unsupported_model")


def test_get_image_generation_config_parses_reference_image_supported_models(monkeypatch) -> None:
    image_config.reset_image_generation_config_cache()

    monkeypatch.setattr(
        image_config,
        "get_config_section",
        lambda section, reload=False: {
            "default_backend": "modelstudio",
            "enabled_backends": '["modelstudio"]',
            "reference_image_supported_models": '{"modelstudio":["foo-model"]}',
        },
    )

    cfg = image_config.get_image_generation_config(reload=True)

    assert cfg.reference_image_supported_models == {"modelstudio": ["foo-model"]}
