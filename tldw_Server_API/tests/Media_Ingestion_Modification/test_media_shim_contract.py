from pathlib import Path


def test_legacy_media_shim_markers_removed_after_n_plus_one_window():
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
    assert 'LEGACY_MEDIA_SHIM_MODE = "adapter_only"' not in source
    assert "_legacy_media = None" not in source
    assert "_process_uploaded_files = _save_uploaded_files" not in source
    assert "async def _process_document_like_item" not in source
