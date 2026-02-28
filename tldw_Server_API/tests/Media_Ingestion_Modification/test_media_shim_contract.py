from pathlib import Path


def test_legacy_media_shim_exposes_adapter_only_marker():
    source_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "media"
        / "__init__.py"
    )
    source = source_path.read_text(encoding="utf-8")
    assert 'LEGACY_MEDIA_SHIM_MODE = "adapter_only"' in source
    assert "_legacy_media = None" in source

