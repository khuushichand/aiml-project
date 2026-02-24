from tldw_Server_API.app.core.Image_Generation.adapters.base import ImageGenRequest
from tldw_Server_API.app.core.Image_Generation.adapters import modelstudio_image_adapter as modelstudio_module
from tldw_Server_API.app.core.Image_Generation.config import ImageGenerationConfig


def _make_config(**overrides) -> ImageGenerationConfig:
    base = dict(
        default_backend="modelstudio",
        enabled_backends=["modelstudio"],
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
        modelstudio_image_base_url="https://dashscope-intl.aliyuncs.com/api/v1",
        modelstudio_image_api_key="sk-modelstudio",
        modelstudio_image_default_model="qwen-image",
        modelstudio_image_region="sg",
        modelstudio_image_mode="sync",
        modelstudio_image_poll_interval_seconds=2,
        modelstudio_image_timeout_seconds=180,
        modelstudio_image_allowed_extra_params=[],
    )
    base.update(overrides)
    return ImageGenerationConfig(**base)


def _make_request(**overrides) -> ImageGenRequest:
    base = dict(
        backend="modelstudio",
        prompt="draw a cat",
        negative_prompt=None,
        width=1024,
        height=1024,
        steps=None,
        cfg_scale=None,
        seed=None,
        sampler=None,
        model=None,
        format="png",
        extra_params={},
        request_id=None,
    )
    base.update(overrides)
    return ImageGenRequest(**base)


def test_modelstudio_generate_sync_data_url(monkeypatch):
    cfg = _make_config()
    monkeypatch.setattr(modelstudio_module, "get_image_generation_config", lambda: cfg)

    captured = {}

    def fake_fetch_json(method, url, headers, json, timeout, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"image_url": "data:image/png;base64,aGVsbG8="},
                            ]
                        }
                    }
                ]
            }
        }

    monkeypatch.setattr(modelstudio_module, "fetch_json", fake_fetch_json)

    adapter = modelstudio_module.ModelStudioImageAdapter()
    result = adapter.generate(_make_request())
    assert result.content == b"hello"
    assert result.content_type == "image/png"
    assert result.bytes_len == 5
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/services/aigc/multimodal-generation/generation")
