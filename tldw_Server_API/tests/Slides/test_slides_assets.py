import base64
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.Slides.slides_assets import (
    SlidesAssetError,
    parse_slide_asset_ref,
    resolve_slide_asset,
)


def test_parse_slide_asset_ref_accepts_output_refs():
    assert parse_slide_asset_ref("output:123") == ("output", 123)


def test_resolve_slide_asset_reads_output_artifact_bytes(tmp_path, monkeypatch):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    file_path = outputs_dir / "cover.png"
    raw_bytes = b"png-bytes"
    file_path.write_bytes(raw_bytes)

    fake_db = SimpleNamespace(
        get_output_artifact=lambda output_id: SimpleNamespace(
            id=output_id,
            format="png",
            storage_path="cover.png",
            metadata_json=None,
            title="Cover",
            type="generated_image",
        ),
        resolve_output_storage_path=lambda path_value: str(path_value),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.slides_assets._resolve_output_path_for_user",
        lambda user_id, path_value: file_path,
    )

    resolved = resolve_slide_asset("output:123", collections_db=fake_db, user_id=1)

    assert resolved["mime"] == "image/png"
    assert base64.b64decode(resolved["data_b64"]) == raw_bytes
    assert resolved["download_path"] == "/api/v1/outputs/123/download"


def test_resolve_slide_asset_requires_user_context_for_output_refs():
    with pytest.raises(SlidesAssetError) as exc:
        resolve_slide_asset("output:123")

    assert exc.value.code == "slide_asset_context_required"
