import hashlib
import json
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Setup.audio_pack_service import (
    build_audio_pack_manifest,
    get_audio_pack_root,
    resolve_audio_pack_path,
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


def test_audio_pack_manifest_streams_asset_checksums(monkeypatch, tmp_path):
    asset_path = tmp_path / "model.bin"
    asset_bytes = b"audio-pack-asset"
    asset_path.write_bytes(asset_bytes)

    def _fail_read_bytes(self):  # noqa: ANN001
        raise AssertionError("read_bytes should not be used for audio pack checksums")

    monkeypatch.setattr(Path, "read_bytes", _fail_read_bytes)

    manifest = build_audio_pack_manifest(
        bundle_id="cpu_local",
        resource_profile="balanced",
        installed_assets=[{"path": str(asset_path)}],
    )

    assert manifest["checksums"]["assets"][str(asset_path)] == hashlib.sha256(asset_bytes).hexdigest()


def test_validate_audio_pack_manifest_reports_platform_mismatch(tmp_path, monkeypatch):
    monkeypatch_root = tmp_path / "Config_Files"
    manifest = build_audio_pack_manifest(
        bundle_id="cpu_local",
        resource_profile="balanced",
        catalog_version="v2",
        compatibility={"platform": "linux", "arch": "x86_64", "python_version": "3.11"},
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Setup.audio_pack_service.CONFIG_ROOT",
        monkeypatch_root,
    )
    pack_path = resolve_audio_pack_path("audio_pack.json")
    pack_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_audio_pack_manifest(
        "audio_pack.json",
        machine_profile={"platform": "darwin", "arch": "arm64"},
        python_version="3.11.13",
    )

    assert result["compatible"] is False
    assert any("platform" in issue.lower() for issue in result["issues"])


def test_validate_audio_pack_manifest_rejects_non_object_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Setup.audio_pack_service.CONFIG_ROOT",
        tmp_path / "Config_Files",
    )
    pack_path = resolve_audio_pack_path("bad-pack.json")
    pack_path.write_text(json.dumps(["not", "a", "manifest"]), encoding="utf-8")

    result = validate_audio_pack_manifest("bad-pack.json")

    assert result["compatible"] is False
    assert "Audio pack manifest must be a JSON object." in result["issues"]


def test_validate_audio_pack_manifest_handles_invalid_nested_shapes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Setup.audio_pack_service.CONFIG_ROOT",
        tmp_path / "Config_Files",
    )
    pack_path = resolve_audio_pack_path("odd-pack.json")
    pack_path.write_text(
        json.dumps(
            {
                "format": "audio_bundle_pack_manifest_v1",
                "bundle_id": 123,
                "resource_profile": ["balanced"],
                "catalog_version": "v2",
                "selection_key": "v2:cpu_local:balanced",
                "compatibility": ["linux", "x86_64"],
                "assets": ["not-a-dict"],
                "checksums": [],
            }
        ),
        encoding="utf-8",
    )

    result = validate_audio_pack_manifest("odd-pack.json")

    assert result["compatible"] is False
    assert "Manifest checksums entry must be an object." in result["issues"]
    assert "Manifest compatibility entry must be an object." in result["issues"]
    assert "Referenced audio bundle or resource profile is not available in this catalog." in result["issues"]


def test_resolve_audio_pack_path_anchors_to_managed_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Setup.audio_pack_service.CONFIG_ROOT",
        tmp_path / "Config_Files",
    )

    resolved = resolve_audio_pack_path("bundle-pack.json")

    assert resolved == tmp_path / "Config_Files" / "audio_packs" / "bundle-pack.json"
    assert get_audio_pack_root() == tmp_path / "Config_Files" / "audio_packs"


def test_resolve_audio_pack_path_returns_resolved_managed_path(tmp_path, monkeypatch):
    config_root = tmp_path / "nested" / ".." / "Config_Files"
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Setup.audio_pack_service.CONFIG_ROOT",
        config_root,
    )

    resolved = resolve_audio_pack_path("bundle-pack.json")

    assert resolved == (tmp_path / "Config_Files" / "audio_packs" / "bundle-pack.json").resolve()


@pytest.mark.parametrize("pack_name", ["../bundle.json", "nested/bundle.json", "nested\\bundle.json", ".json"])
def test_resolve_audio_pack_path_rejects_non_filename_inputs(pack_name):
    with pytest.raises(ValueError, match="Audio pack names must"):
        resolve_audio_pack_path(pack_name)
