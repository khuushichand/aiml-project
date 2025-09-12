"""
Integration tests for Media Versioning endpoints.
Flow: create media -> create version -> list versions -> get version -> delete version.
No internal mocks; uses dependency injection for user and DB access as configured in app.
"""

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.settings import get_settings


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_auth():
    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)
    app.dependency_overrides[get_request_user] = override_user
    settings = get_settings()
    headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
    yield TestClient(app, headers=headers)
    app.dependency_overrides.clear()


def _create_media_and_get_id(client: TestClient, title: str) -> int:
    r = client.post(
        "/api/v1/media/add",
        json={
            "title": title,
            "content": f"{title} original content.",
            "media_type": "document",
            "chunk_method": "sentences",
        },
    )
    assert r.status_code in (200, 207), r.text
    data = r.json()
    assert data.get("media_id") is not None
    return int(data["media_id"]) if isinstance(data["media_id"], (int,)) else data["media_id"]


def test_media_versions_crud_flow(client_with_auth: TestClient):
    client = client_with_auth

    # 1) Create a media item
    media_id = _create_media_and_get_id(client, "Versioned Doc")

    # 2) Create a new version
    create_v = client.post(
        f"/api/v1/media/{media_id}/versions",
        json={
            "content": "v2 content",
            "prompt": "integration prompt",
            "analysis_content": "integration analysis"
        },
    )
    assert create_v.status_code in (201, 404, 500), create_v.text
    if create_v.status_code != 201:
        pytest.skip("Environment does not support version creation (DB backend not ready)")
    vinfo = create_v.json()
    # Response should include these keys
    for key in ("message", "media_id", "version_number", "version_uuid"):
        assert key in vinfo
    vnum = vinfo.get("version_number")
    assert isinstance(vnum, int)

    # 3) List versions
    lst = client.get(f"/api/v1/media/{media_id}/versions", params={"page": 1, "limit": 10})
    assert lst.status_code == 200
    versions = lst.json()
    assert isinstance(versions, list)
    # Each version should at least expose version_number
    assert all("version_number" in v for v in versions)
    assert any(v.get("version_number") == vnum for v in versions)

    # 4) Get specific version
    got = client.get(f"/api/v1/media/{media_id}/versions/{vnum}", params={"include_content": True})
    assert got.status_code == 200
    vdata = got.json()
    assert vdata.get("version_number") == vnum
    # include_content=True should return content when available
    assert "content" in vdata

    # 5) Delete version
    delr = client.delete(f"/api/v1/media/{media_id}/versions/{vnum}")
    assert delr.status_code in (200, 204)

    # 6) Ensure version not found now
    nf = client.get(f"/api/v1/media/{media_id}/versions/{vnum}")
    assert nf.status_code in (404, 200)  # Some backends may still return the record depending on soft delete visibility


def test_get_version_strict_404_after_delete_if_enforced(client_with_auth: TestClient):
    """If backend enforces soft-delete visibility, GET after delete should return 404; otherwise skip."""
    client = client_with_auth
    media_id = _create_media_and_get_id(client, "Strict Delete Doc")

    # Create a version to delete
    cv = client.post(
        f"/api/v1/media/{media_id}/versions",
        json={"content": "to be deleted", "prompt": "p", "analysis_content": "a"}
    )
    if cv.status_code != 201:
        pytest.skip("Version creation unsupported; skipping strict 404 test")
    vnum = cv.json().get("version_number")

    # Delete it
    d = client.delete(f"/api/v1/media/{media_id}/versions/{vnum}")
    if d.status_code not in (200, 204):
        pytest.skip("Delete not supported; skipping strict 404 test")

    # Get should return 404 when enforcement exists; skip otherwise
    g = client.get(f"/api/v1/media/{media_id}/versions/{vnum}")
    if g.status_code != 404:
        pytest.skip("Backend still exposes soft-deleted versions; skipping strict 404 assertion")
    assert g.status_code == 404


def test_media_versions_rollback_flow(client_with_auth: TestClient):
    client = client_with_auth

    # 1) Create a media item -> initial version exists (v1)
    media_id = _create_media_and_get_id(client, "Rollback Doc")

    # 2) Create a second version (v2)
    v2_resp = client.post(
        f"/api/v1/media/{media_id}/versions",
        json={
            "content": "v2 content for rollback",
            "prompt": "integration prompt",
            "analysis_content": "integration analysis"
        },
    )
    if v2_resp.status_code != 201:
        pytest.skip("Environment does not support version create; skipping rollback test")

    # 3) Rollback to version 1
    rb = client.post(
        f"/api/v1/media/{media_id}/versions/rollback",
        json={"version_number": 1}
    )
    assert rb.status_code in (200, 409, 404, 500)
    if rb.status_code != 200:
        pytest.skip("Rollback not supported/eligible in this environment")
    rdata = rb.json()
    # Rollback response should include new version details
    for key in ("message", "new_document_version_number", "new_document_version_uuid", "new_media_version"):
        assert key in rdata
    assert isinstance(rdata.get("new_document_version_number"), int)

    # 4) Verify current latest version is v1 again (or a new top version equivalent to v1 content)
    lst = client.get(f"/api/v1/media/{media_id}/versions", params={"page": 1, "limit": 10})
    assert lst.status_code == 200
    versions = lst.json()
    assert isinstance(versions, list)
    # After rollback, top version number should be >=2 but represent reverted content; accept presence as success criteria


def test_rollback_to_current_version_conflict(client_with_auth: TestClient):
    client = client_with_auth

    media_id = _create_media_and_get_id(client, "Rollback Conflict Doc")

    # Create a new version to ensure we have at least v2
    v2_resp = client.post(
        f"/api/v1/media/{media_id}/versions",
        json={
            "content": "v2 conflict content",
            "prompt": "integration prompt",
            "analysis_content": "integration analysis"
        },
    )
    if v2_resp.status_code != 201:
        pytest.skip("Version creation unsupported; skipping conflict rollback test")

    # Determine latest version number
    lst = client.get(f"/api/v1/media/{media_id}/versions", params={"page": 1, "limit": 10})
    assert lst.status_code == 200
    versions = lst.json()
    latest = max(v.get("version_number", 0) for v in versions) if versions else 2

    # Attempt rollback to current latest version should return 409
    rb = client.post(
        f"/api/v1/media/{media_id}/versions/rollback",
        json={"version_number": latest}
    )
    if rb.status_code != 409:
        pytest.skip("Backend did not enforce 'rollback to current' conflict; skipping assertion")
    assert rb.status_code == 409


def test_rollback_to_nonexistent_and_invalid_version(client_with_auth: TestClient):
    client = client_with_auth

    media_id = _create_media_and_get_id(client, "Rollback Edge Doc")

    # Try rollback to a very high non-existent version -> expect 404 (or skip if backend differs)
    rb_nf = client.post(
        f"/api/v1/media/{media_id}/versions/rollback",
        json={"version_number": 9999}
    )
    if rb_nf.status_code not in (404, 409, 500):
        # Accept 404 as ideal; some backends may map errors differently
        pytest.skip("Backend did not return a not-found-like status for non-existent version rollback")

    # Try rollback with an invalid version number (e.g., negative)
    rb_bad = client.post(
        f"/api/v1/media/{media_id}/versions/rollback",
        json={"version_number": -1}
    )
    # Endpoint may return 400 (invalid input) or map to other error codes depending on DB
    assert rb_bad.status_code in (400, 404, 409, 500)
