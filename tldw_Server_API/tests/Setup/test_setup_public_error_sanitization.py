from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import tldw_Server_API.app.api.v1.endpoints.setup as setup_endpoint


@pytest.mark.asyncio
async def test_execute_audio_bundle_provision_hides_internal_validation_details(mocker):
    mocker.patch.object(setup_endpoint, "_ensure_audio_installer_available", return_value=None)
    mocker.patch.object(
        setup_endpoint.install_manager,
        "execute_audio_bundle",
        side_effect=ValueError("config=/Users/private/audio-bundle.yml"),
    )

    with pytest.raises(HTTPException) as excinfo:
        await setup_endpoint._execute_audio_bundle_provision(
            setup_endpoint.AudioBundleProvisionRequest(
                bundle_id="cpu_local",
                resource_profile="balanced",
            )
        )

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == setup_endpoint.INVALID_AUDIO_BUNDLE_REQUEST_DETAIL
    assert excinfo.value.__cause__ is None


@pytest.mark.asyncio
async def test_execute_audio_bundle_verification_hides_internal_lookup_details(mocker):
    mocker.patch.object(setup_endpoint, "_ensure_audio_installer_available", return_value=None)
    mocker.patch.object(
        setup_endpoint.install_manager,
        "verify_audio_bundle_async",
        AsyncMock(side_effect=KeyError("Unknown bundle '/Users/private/catalog.json'")),
    )

    with pytest.raises(HTTPException) as excinfo:
        await setup_endpoint._execute_audio_bundle_verification(
            setup_endpoint.AudioBundleVerificationRequest(
                bundle_id="cpu_local",
                resource_profile="balanced",
            )
        )

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == setup_endpoint.AUDIO_BUNDLE_NOT_FOUND_DETAIL
    assert excinfo.value.__cause__ is None


@pytest.mark.asyncio
async def test_export_audio_pack_hides_internal_manifest_errors(mocker):
    mocker.patch.object(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        return_value={"enabled": True, "needs_setup": True},
    )
    mocker.patch.object(
        setup_endpoint.audio_readiness_store,
        "get_audio_readiness_store",
        return_value=SimpleNamespace(load=lambda: {}),
    )
    mocker.patch.object(
        setup_endpoint.audio_profile_service,
        "detect_machine_profile",
        return_value=SimpleNamespace(model_dump=lambda: {"platform": "linux"}),
    )
    mocker.patch.object(
        setup_endpoint.audio_pack_service,
        "build_audio_pack_manifest",
        side_effect=ValueError("manifest write failed at /Users/private/audio-pack.json"),
    )

    with pytest.raises(HTTPException) as excinfo:
        await setup_endpoint.export_audio_pack(
            setup_endpoint.AudioPackExportRequest(
                bundle_id="cpu_local",
                resource_profile="balanced",
            ),
            _guard=None,
        )

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == setup_endpoint.INVALID_AUDIO_PACK_EXPORT_REQUEST_DETAIL
    assert excinfo.value.__cause__ is None
