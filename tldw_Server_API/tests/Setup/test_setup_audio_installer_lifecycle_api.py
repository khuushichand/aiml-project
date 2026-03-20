from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.main import app
import tldw_Server_API.app.api.v1.endpoints.setup as setup_endpoint


def _make_client():
    return TestClient(app)


class _BundleCatalogStub:
    def __init__(self) -> None:
        self.bundles = [SimpleNamespace(bundle_id="cpu_local", model_dump=lambda: {"bundle_id": "cpu_local"})]


@pytest.fixture()
def _admin_audio_installer_setup(monkeypatch):
    async def fake_get_auth_principal(_request):
        return AuthPrincipal(
            kind="user",
            user_id=7,
            roles=["admin"],
            permissions=["system.configure"],
            is_admin=False,
        )

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.API_Deps.auth_deps.get_auth_principal",
        fake_get_auth_principal,
    )
    monkeypatch.setattr(
        setup_endpoint.audio_profile_service,
        "detect_machine_profile",
        lambda: {
            "platform": "darwin",
            "arch": "arm64",
            "apple_silicon": True,
            "cuda_available": False,
            "ffmpeg_available": True,
            "espeak_available": True,
            "free_disk_gb": 64.0,
            "network_available_for_downloads": True,
        },
    )
    monkeypatch.setattr(
        setup_endpoint.audio_profile_service,
        "recommend_audio_bundles",
        lambda *args, **kwargs: {"recommendations": [], "excluded": []},
    )
    monkeypatch.setattr(setup_endpoint, "get_audio_bundle_catalog", lambda: _BundleCatalogStub())
    monkeypatch.setattr(
        setup_endpoint.install_manager,
        "get_install_status_snapshot",
        lambda: {"status": "idle"},
    )
    monkeypatch.setattr(
        setup_endpoint.install_manager,
        "execute_audio_bundle",
        lambda bundle_id, resource_profile, safe_rerun=False: {
            "status": "completed",
            "bundle_id": bundle_id,
            "resource_profile": resource_profile,
            "safe_rerun": safe_rerun,
        },
    )

    async def _fake_verify_audio_bundle_async(bundle_id, resource_profile):
        return {
            "status": "ready",
            "bundle_id": bundle_id,
            "resource_profile": resource_profile,
        }

    monkeypatch.setattr(
        setup_endpoint.install_manager,
        "verify_audio_bundle_async",
        _fake_verify_audio_bundle_async,
    )


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("get", "/api/v1/setup/admin/install-status", None),
        ("get", "/api/v1/setup/admin/audio/recommendations", None),
        (
            "post",
            "/api/v1/setup/admin/audio/provision",
            {"bundle_id": "cpu_local", "resource_profile": "balanced"},
        ),
        (
            "post",
            "/api/v1/setup/admin/audio/verify",
            {"bundle_id": "cpu_local", "resource_profile": "balanced"},
        ),
    ],
)
def test_admin_audio_installer_routes_remain_available_after_setup_completed(
    monkeypatch,
    _admin_audio_installer_setup,
    method,
    path,
    json_body,
):
    monkeypatch.setattr(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        lambda: {"enabled": False, "setup_completed": True, "needs_setup": False},
    )

    request_kwargs = {"json": json_body} if json_body is not None else {}
    with _make_client() as client:
        response = getattr(client, method)(path, **request_kwargs)

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("get", "/api/v1/setup/admin/install-status", None),
        ("get", "/api/v1/setup/admin/audio/recommendations", None),
        (
            "post",
            "/api/v1/setup/admin/audio/provision",
            {"bundle_id": "cpu_local", "resource_profile": "balanced"},
        ),
        (
            "post",
            "/api/v1/setup/admin/audio/verify",
            {"bundle_id": "cpu_local", "resource_profile": "balanced"},
        ),
    ],
)
def test_admin_audio_installer_routes_stay_unavailable_without_setup_or_completion(
    monkeypatch,
    _admin_audio_installer_setup,
    method,
    path,
    json_body,
):
    monkeypatch.setattr(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        lambda: {"enabled": False, "setup_completed": False, "needs_setup": False},
    )

    request_kwargs = {"json": json_body} if json_body is not None else {}
    with _make_client() as client:
        response = getattr(client, method)(path, **request_kwargs)

    assert response.status_code == 404
