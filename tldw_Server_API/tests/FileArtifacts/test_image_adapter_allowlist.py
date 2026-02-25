from types import SimpleNamespace

from tldw_Server_API.app.core.File_Artifacts.adapters.image_adapter import ImageAdapter


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
