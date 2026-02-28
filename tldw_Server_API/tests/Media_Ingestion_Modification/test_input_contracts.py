import importlib.util
from pathlib import Path
import sys


def _load_input_contracts_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "media"
        / "input_contracts.py"
    )
    spec = importlib.util.spec_from_file_location(
        "media_input_contracts_test_module",
        module_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_normalize_urls_field_handles_legacy_empty_list_sentinel():
    contracts_module = _load_input_contracts_module()
    assert contracts_module.normalize_urls_field([""]) is None
    assert contracts_module.normalize_urls_field(["https://example.com"]) == [
        "https://example.com"
    ]


def test_validate_media_inputs_delegates_to_provided_callable():
    contracts_module = _load_input_contracts_module()
    calls = []

    def _fake_validator(media_type, urls, files):
        calls.append((media_type, urls, files))

    contracts_module.validate_media_inputs(
        _fake_validator,
        "video",
        ["https://example.com"],
        None,
    )
    assert calls == [("video", ["https://example.com"], None)]

