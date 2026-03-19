import json
import sys

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
import tldw_Server_API.app.api.v1.endpoints.setup as setup_endpoint
from tldw_Server_API.app.core.Setup.audio_profile_service import MachineProfile


def _make_client():
    return TestClient(app)


def test_setup_audio_pack_export_returns_manifest(mocker):
    mocker.patch.object(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        return_value={"enabled": True, "needs_setup": True},
    )
    mocker.patch.object(
        setup_endpoint.audio_profile_service,
        "detect_machine_profile",
        return_value=MachineProfile(
            platform="linux",
            arch="x86_64",
            apple_silicon=False,
            cuda_available=False,
            ffmpeg_available=True,
            espeak_available=True,
            free_disk_gb=64.0,
            network_available_for_downloads=True,
        ),
    )

    with _make_client() as client:
        response = client.post(
            "/api/v1/setup/audio/packs/export",
            json={"bundle_id": "cpu_local", "resource_profile": "balanced"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["manifest"]["bundle_id"] == "cpu_local"
    assert body["manifest"]["resource_profile"] == "balanced"
    assert body["manifest"]["checksums"]["manifest_sha256"]


def test_setup_audio_pack_export_uses_manifest_compatibility_shape(mocker):
    mocker.patch.object(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        return_value={"enabled": True, "needs_setup": True},
    )
    mocker.patch.object(
        setup_endpoint.audio_profile_service,
        "detect_machine_profile",
        return_value=MachineProfile(
            platform="linux",
            arch="x86_64",
            apple_silicon=False,
            cuda_available=False,
            ffmpeg_available=True,
            espeak_available=True,
            free_disk_gb=64.0,
            network_available_for_downloads=True,
        ),
    )

    with _make_client() as client:
        response = client.post(
            "/api/v1/setup/audio/packs/export",
            json={"bundle_id": "cpu_local", "resource_profile": "balanced"},
        )

    assert response.status_code == 200
    assert response.json()["manifest"]["compatibility"] == {
        "platform": "linux",
        "arch": "x86_64",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
    }


def test_setup_audio_pack_import_updates_readiness(mocker, tmp_path):
    store = setup_endpoint.audio_readiness_store.AudioReadinessStore(
        tmp_path / "audio_readiness.json"
    )
    pack_path = tmp_path / "audio_pack.json"
    pack_path.write_text(
        json.dumps(
            {
                "format": "audio_bundle_pack_manifest_v1",
                "bundle_id": "cpu_local",
                "resource_profile": "balanced",
                "catalog_version": "v2",
                "selection_key": "v2:cpu_local:balanced",
                "compatibility": {
                    "platform": "linux",
                    "arch": "x86_64",
                    "python_version": "3.11",
                },
                "checksums": {"manifest_sha256": ""},
            }
        ),
        encoding="utf-8",
    )

    manifest = setup_endpoint.audio_pack_service.build_audio_pack_manifest(
        bundle_id="cpu_local",
        resource_profile="balanced",
        catalog_version="v2",
        compatibility={"platform": "linux", "arch": "x86_64", "python_version": "3.11"},
    )
    pack_path.write_text(json.dumps(manifest), encoding="utf-8")

    mocker.patch.object(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        return_value={"enabled": True, "needs_setup": True},
    )
    mocker.patch.object(
        setup_endpoint.audio_profile_service,
        "detect_machine_profile",
        return_value=MachineProfile(
            platform="linux",
            arch="x86_64",
            apple_silicon=False,
            cuda_available=False,
            ffmpeg_available=True,
            espeak_available=True,
            free_disk_gb=64.0,
            network_available_for_downloads=False,
        ),
    )
    mocker.patch.object(
        setup_endpoint.audio_readiness_store,
        "get_audio_readiness_store",
        return_value=store,
    )

    with _make_client() as client:
        response = client.post(
            "/api/v1/setup/audio/packs/import",
            json={"pack_path": str(pack_path)},
        )
        readiness = client.get("/api/v1/setup/audio/readiness")

    assert response.status_code == 200
    assert response.json()["compatible"] is True
    assert readiness.status_code == 200
    assert readiness.json()["selected_bundle_id"] == "cpu_local"
    assert readiness.json()["selected_resource_profile"] == "balanced"
    assert readiness.json()["imported_packs"][0]["pack_path"] == str(pack_path)


def test_setup_audio_pack_import_rejects_parent_directory_traversal(mocker):
    mocker.patch.object(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        return_value={"enabled": True, "needs_setup": True},
    )

    with _make_client() as client:
        response = client.post(
            "/api/v1/setup/audio/packs/import",
            json={"pack_path": "../audio_pack.json"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Audio pack path must not contain parent directory traversal."


def test_setup_audio_pack_import_masks_missing_path_details(mocker, tmp_path):
    pack_path = tmp_path / "missing_pack.json"
    mocker.patch.object(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        return_value={"enabled": True, "needs_setup": True},
    )

    with _make_client() as client:
        response = client.post(
            "/api/v1/setup/audio/packs/import",
            json={"pack_path": str(pack_path)},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Audio pack not found."
    assert str(pack_path) not in response.text


def test_setup_audio_pack_export_masks_bundle_lookup_details(mocker):
    mocker.patch.object(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        return_value={"enabled": True, "needs_setup": True},
    )
    mocker.patch.object(
        setup_endpoint.audio_profile_service,
        "detect_machine_profile",
        return_value=MachineProfile(
            platform="linux",
            arch="x86_64",
            apple_silicon=False,
            cuda_available=False,
            ffmpeg_available=True,
            espeak_available=True,
            free_disk_gb=64.0,
            network_available_for_downloads=True,
        ),
    )
    mocker.patch.object(
        setup_endpoint.audio_pack_service,
        "build_audio_pack_manifest",
        side_effect=KeyError("catalog internals"),
    )

    with _make_client() as client:
        response = client.post(
            "/api/v1/setup/audio/packs/export",
            json={"bundle_id": "cpu_local", "resource_profile": "balanced"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Audio bundle or resource profile not found."
