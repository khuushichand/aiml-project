import json

from tldw_Server_API.app.core.Setup.audio_pack_service import (
    build_audio_pack_manifest,
    validate_audio_pack_manifest,
)


def test_audio_pack_manifest_captures_selection_identity():
    manifest = build_audio_pack_manifest(
        bundle_id="cpu_local",
        resource_profile="balanced",
        catalog_version="v2",
    )

    assert manifest["bundle_id"] == "cpu_local"
    assert manifest["resource_profile"] == "balanced"
    assert manifest["selection_key"] == "v2:cpu_local:balanced"
    assert "checksums" in manifest
    assert manifest["checksums"]["manifest_sha256"]


def test_validate_audio_pack_manifest_reports_platform_mismatch(tmp_path):
    manifest = build_audio_pack_manifest(
        bundle_id="cpu_local",
        resource_profile="balanced",
        catalog_version="v2",
        compatibility={"platform": "linux", "arch": "x86_64", "python_version": "3.11"},
    )
    pack_path = tmp_path / "audio_pack.json"
    pack_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_audio_pack_manifest(
        pack_path,
        machine_profile={"platform": "darwin", "arch": "arm64"},
        python_version="3.11.13",
    )

    assert result["compatible"] is False
    assert any("platform" in issue.lower() for issue in result["issues"])
