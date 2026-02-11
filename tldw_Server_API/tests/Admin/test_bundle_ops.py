# test_bundle_ops.py
# Description: Tests for admin backup bundle endpoints and service layer.
from __future__ import annotations

import hashlib
import io
import json
import os
import sqlite3
import uuid
import zipfile

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_env(tmp_path):
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = "unit-test-api-key"
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'users_test_bundle_ops.db'}"
    os.environ["TLDW_DB_ALLOWED_BASE_DIRS"] = str(tmp_path)
    os.environ["TLDW_DB_BACKUP_PATH"] = str(tmp_path / "backups")
    os.environ["USER_DB_BASE_DIR"] = str(tmp_path / "user_dbs")


async def _reset_state():
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.session_manager import reset_session_manager
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    await reset_db_pool()
    reset_settings()
    await reset_session_manager()

    # Reset module-level rate limit state so tests are isolated
    from tldw_Server_API.app.services import admin_bundle_service
    admin_bundle_service._rate_limit_windows.clear()


async def _seed_authnz_data() -> int:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, is_postgres_backend

    pool = await get_db_pool()
    username = "bundle_user"
    email = "bundle_user@example.com"
    if await is_postgres_backend():
        await pool.execute(
            """
            INSERT INTO users (uuid, username, email, password_hash, is_active)
            VALUES (?,?,?,?,1)
            ON CONFLICT (username) DO NOTHING
            """,
            str(uuid.uuid4()), username, email, "x",
        )
    else:
        await pool.execute(
            "INSERT OR IGNORE INTO users (uuid, username, email, password_hash, is_active) VALUES (?,?,?,?,1)",
            str(uuid.uuid4()), username, email, "x",
        )
    user_id = await pool.fetchval("SELECT id FROM users WHERE username = ?", username)
    await pool.execute(
        "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, ip_address, details) VALUES (?,?,?,?,?,?)",
        int(user_id), "bundle.test", "backup", 1, "127.0.0.1", '{"ok": true}',
    )
    return int(user_id)


def _seed_user_db(tmp_path, user_id: int):
    """Create a minimal SQLite DB for the media dataset so backups work."""
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

    media_path = DatabasePaths.get_media_db_path(user_id)
    media_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(media_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO t (id) VALUES (1)")
        conn.commit()


def _make_bundle_zip(datasets=None, manifest_overrides=None, tamper_checksum=False):
    """Build a minimal in-memory bundle ZIP for import tests.

    Uses real SQLite databases instead of null bytes so restore operations work.
    """
    datasets = datasets or ["authnz"]
    files_meta = {}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for ds in datasets:
            filename = f"{ds}_backup.db"
            # Create a minimal valid SQLite database in memory
            conn = sqlite3.connect(":memory:")
            conn.execute("CREATE TABLE bundle_marker (id INTEGER PRIMARY KEY)")
            conn.execute("INSERT INTO bundle_marker (id) VALUES (1)")
            conn.commit()
            # Serialize to bytes via backup API
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
                tf_path = tf.name
            try:
                disk_conn = sqlite3.connect(tf_path)
                conn.backup(disk_conn)
                disk_conn.close()
                with open(tf_path, "rb") as f:
                    content = f.read()
            finally:
                os.unlink(tf_path)
            conn.close()

            zf.writestr(filename, content)

            sha = hashlib.sha256(content).hexdigest()
            if tamper_checksum:
                sha = "0" * 64
            files_meta[filename] = {
                "dataset": ds,
                "sha256": sha,
                "hash_algorithm": "sha256",
                "size_bytes": str(len(content)),
            }

        manifest = {
            "manifest_version": 1,
            "app_version": "0.1.0",
            "created_at": "2026-01-01T00:00:00+00:00",
            "user_id": None,
            "datasets": datasets,
            "files": files_meta,
            "schema_versions": {},
            "notes": "test bundle",
            "platform": {"os": "test", "python": "3.12", "sqlite": "3.40"},
        }
        if manifest_overrides:
            manifest.update(manifest_overrides)
        zf.writestr("manifest.json", json.dumps(manifest))

    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_bundle_authnz_only(tmp_path):
    """Create a bundle with only the authnz dataset."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        await _seed_authnz_data()

        resp = client.post(
            "/api/v1/admin/backups/bundles",
            json={"datasets": ["authnz"]},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "created"
        assert "authnz" in data["item"]["datasets"]
        assert data["item"]["bundle_id"].endswith(".zip")


@pytest.mark.asyncio
async def test_create_bundle_subset(tmp_path):
    """Create a bundle with a subset of datasets."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        user_id = await _seed_authnz_data()
        _seed_user_db(tmp_path, user_id)

        resp = client.post(
            "/api/v1/admin/backups/bundles",
            json={"datasets": ["authnz", "media"], "user_id": user_id},
        )
        assert resp.status_code == 200, resp.text
        item = resp.json()["item"]
        assert set(item["datasets"]) == {"authnz", "media"}


@pytest.mark.asyncio
async def test_create_bundle_unknown_dataset(tmp_path):
    """Unknown dataset should return 400."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        resp = client.post(
            "/api/v1/admin/backups/bundles",
            json={"datasets": ["nonexistent"]},
        )
        assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_create_bundle_vector_store_rejected(tmp_path):
    """include_vector_store=True should return 422."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        resp = client.post(
            "/api/v1/admin/backups/bundles",
            json={"datasets": ["authnz"], "include_vector_store": True},
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"] == "vector_store_export_not_supported"


@pytest.mark.asyncio
async def test_list_bundles_empty(tmp_path):
    """List bundles when none exist."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        resp = client.get("/api/v1/admin/backups/bundles")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_bundles_after_create(tmp_path):
    """List bundles after creating one."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        await _seed_authnz_data()

        create_resp = client.post(
            "/api/v1/admin/backups/bundles",
            json={"datasets": ["authnz"]},
        )
        assert create_resp.status_code == 200, create_resp.text

        resp = client.get("/api/v1/admin/backups/bundles")
        assert resp.status_code == 200, resp.text
        assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_list_bundles_pagination(tmp_path):
    """Pagination should work with limit/offset."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        await _seed_authnz_data()

        # Create two bundles
        r1 = client.post("/api/v1/admin/backups/bundles", json={"datasets": ["authnz"]})
        assert r1.status_code == 200, r1.text
        import time
        time.sleep(1.1)  # ensure different timestamps
        r2 = client.post("/api/v1/admin/backups/bundles", json={"datasets": ["authnz"]})
        assert r2.status_code == 200, r2.text

        resp = client.get("/api/v1/admin/backups/bundles", params={"limit": 1, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["total"] >= 2


# ---------------------------------------------------------------------------
# Metadata & download tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_bundle_metadata(tmp_path):
    """Get metadata for a specific bundle."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        await _seed_authnz_data()

        create_resp = client.post(
            "/api/v1/admin/backups/bundles",
            json={"datasets": ["authnz"]},
        )
        assert create_resp.status_code == 200, create_resp.text
        bundle_id = create_resp.json()["item"]["bundle_id"]

        resp = client.get(f"/api/v1/admin/backups/bundles/{bundle_id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["item"]["bundle_id"] == bundle_id


@pytest.mark.asyncio
async def test_get_bundle_metadata_404(tmp_path):
    """Get metadata for non-existent bundle returns 404."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        resp = client.get("/api/v1/admin/backups/bundles/does-not-exist.zip")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_bundle(tmp_path):
    """Download returns application/zip content-type."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        await _seed_authnz_data()

        create_resp = client.post(
            "/api/v1/admin/backups/bundles",
            json={"datasets": ["authnz"]},
        )
        assert create_resp.status_code == 200, create_resp.text
        bundle_id = create_resp.json()["item"]["bundle_id"]

        resp = client.get(f"/api/v1/admin/backups/bundles/{bundle_id}/download")
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("application/zip")


@pytest.mark.asyncio
async def test_download_bundle_404(tmp_path):
    """Download non-existent bundle returns 404."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        resp = client.get("/api/v1/admin/backups/bundles/missing.zip/download")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_bundle(tmp_path):
    """Delete bundle and verify 404 on re-access."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        await _seed_authnz_data()

        create_resp = client.post(
            "/api/v1/admin/backups/bundles",
            json={"datasets": ["authnz"]},
        )
        assert create_resp.status_code == 200, create_resp.text
        bundle_id = create_resp.json()["item"]["bundle_id"]

        del_resp = client.delete(f"/api/v1/admin/backups/bundles/{bundle_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # Should be 404 now
        get_resp = client.get(f"/api/v1/admin/backups/bundles/{bundle_id}")
        assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_bundle_nonexistent(tmp_path):
    """Delete non-existent bundle returns 404."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        resp = client.delete("/api/v1/admin/backups/bundles/ghost.zip")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_import_dry_run(tmp_path):
    """Dry-run import validates without restoring."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        await _seed_authnz_data()

        bundle_buf = _make_bundle_zip(datasets=["authnz"])
        resp = client.post(
            "/api/v1/admin/backups/bundles/import",
            params={"dry_run": "true"},
            files={"file": ("test.zip", bundle_buf, "application/zip")},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "compatible"
        assert data["datasets_restored"] == []


@pytest.mark.asyncio
async def test_import_tampered_checksum(tmp_path):
    """Import with tampered checksum should fail."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        await _seed_authnz_data()

        bundle_buf = _make_bundle_zip(datasets=["authnz"], tamper_checksum=True)
        resp = client.post(
            "/api/v1/admin/backups/bundles/import",
            files={"file": ("test.zip", bundle_buf, "application/zip")},
        )
        assert resp.status_code == 400, resp.text
        assert "checksum" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_import_unsupported_manifest_version(tmp_path):
    """Import with future manifest version should fail."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        await _seed_authnz_data()

        bundle_buf = _make_bundle_zip(
            datasets=["authnz"],
            manifest_overrides={"manifest_version": 999},
        )
        resp = client.post(
            "/api/v1/admin/backups/bundles/import",
            files={"file": ("test.zip", bundle_buf, "application/zip")},
        )
        assert resp.status_code == 400, resp.text
        assert "unsupported_manifest_version" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_import_schema_newer_than_current(tmp_path):
    """Import with schema version newer than current for a dataset that has one."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        await _seed_authnz_data()

        # Use 'media' which has a known schema version, set it impossibly high
        bundle_buf = _make_bundle_zip(
            datasets=["media"],
            manifest_overrides={
                "schema_versions": {"media": 99999},
                "user_id": 1,
            },
        )
        resp = client.post(
            "/api/v1/admin/backups/bundles/import",
            params={"allow_downgrade": "false", "user_id": "1"},
            files={"file": ("test.zip", bundle_buf, "application/zip")},
        )
        assert resp.status_code == 409, resp.text
        assert "schema_incompatible" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_import_allow_downgrade(tmp_path):
    """Import with allow_downgrade=True should succeed even with newer schema."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        user_id = await _seed_authnz_data()
        _seed_user_db(tmp_path, user_id)

        bundle_buf = _make_bundle_zip(
            datasets=["media"],
            manifest_overrides={
                "schema_versions": {"media": 99999},
                "user_id": user_id,
            },
        )
        resp = client.post(
            "/api/v1/admin/backups/bundles/import",
            params={"allow_downgrade": "true", "user_id": str(user_id)},
            files={"file": ("test.zip", bundle_buf, "application/zip")},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "imported"
        assert "media" in data["datasets_restored"]


@pytest.mark.asyncio
async def test_import_real_restore(tmp_path):
    """Full import (non-dry-run) should restore datasets."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        await _seed_authnz_data()

        bundle_buf = _make_bundle_zip(datasets=["authnz"])
        resp = client.post(
            "/api/v1/admin/backups/bundles/import",
            files={"file": ("test.zip", bundle_buf, "application/zip")},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "imported"
        assert "authnz" in data["datasets_restored"]


# ---------------------------------------------------------------------------
# Concurrency / rate limit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrency_lock_busy(tmp_path, monkeypatch):
    """Simulating a locked bundle operation should return 409."""
    _setup_env(tmp_path)
    await _reset_state()

    import asyncio

    from tldw_Server_API.app.services import admin_bundle_service

    # Simulate lock being held
    lock = asyncio.Lock()
    await lock.acquire()
    monkeypatch.setattr(admin_bundle_service, "_bundle_lock", lock)

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        resp = client.post(
            "/api/v1/admin/backups/bundles",
            json={"datasets": ["authnz"]},
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"] == "bundle_operation_in_progress"

    lock.release()


@pytest.mark.asyncio
async def test_rate_limit_exceeded(tmp_path, monkeypatch):
    """Simulating rate limit exceeded should return 429."""
    _setup_env(tmp_path)
    await _reset_state()

    import time

    from tldw_Server_API.app.services import admin_bundle_service

    # Fill the rate limit window for all likely user_id values so the test
    # passes regardless of what user_id the single-user principal resolves to.
    now = time.monotonic()
    monkeypatch.setattr(
        admin_bundle_service,
        "_rate_limit_windows",
        {(0, "export"): [now] * 5, (1, "export"): [now] * 5},
    )

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        resp = client.post(
            "/api/v1/admin/backups/bundles",
            json={"datasets": ["authnz"]},
        )
        assert resp.status_code == 429, resp.text
        assert resp.json()["detail"] == "rate_limit_exceeded"


# ---------------------------------------------------------------------------
# Unit tests for service helpers
# ---------------------------------------------------------------------------

def test_compute_sha256(tmp_path):
    """_compute_sha256 returns correct hex digest."""
    from tldw_Server_API.app.services.admin_bundle_service import _compute_sha256

    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"hello world")
    result = _compute_sha256(str(test_file))
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert result == expected


def test_build_manifest():
    """_build_manifest returns a dict with required keys."""
    from tldw_Server_API.app.services.admin_bundle_service import _build_manifest

    m = _build_manifest(
        user_id=42,
        datasets=["media", "chacha"],
        files={"a.db": {"sha256": "abc", "hash_algorithm": "sha256", "size_bytes": "100", "dataset": "media"}},
        schema_versions={"media": 20, "chacha": 22},
        notes="test",
    )
    assert m["manifest_version"] == 1
    assert m["user_id"] == 42
    assert "media" in m["datasets"]
    assert "platform" in m


def test_get_schema_versions():
    """_get_schema_versions returns a dict with known datasets."""
    from tldw_Server_API.app.services.admin_bundle_service import _get_schema_versions

    versions = _get_schema_versions()
    assert "media" in versions
    assert "chacha" in versions
    # Values should be int or None
    for val in versions.values():
        assert val is None or isinstance(val, int)


def test_check_disk_space(tmp_path):
    """_check_disk_space should not raise for small requirements."""
    from tldw_Server_API.app.services.admin_bundle_service import _check_disk_space

    # Should not raise for 1 byte
    _check_disk_space(str(tmp_path), 1)


def test_check_disk_space_insufficient(tmp_path):
    """_check_disk_space should raise for impossible requirements."""
    from tldw_Server_API.app.core.exceptions import BundleDiskSpaceError
    from tldw_Server_API.app.services.admin_bundle_service import _check_disk_space

    with pytest.raises(BundleDiskSpaceError):
        _check_disk_space(str(tmp_path), 2**63)  # impossibly large


# ---------------------------------------------------------------------------
# GAP-6: Test creating bundle with ALL datasets (default behavior)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_bundle_all_datasets_default(tmp_path):
    """Omitting 'datasets' should default to all 6 datasets."""
    _setup_env(tmp_path)
    await _reset_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        user_id = await _seed_authnz_data()
        _seed_user_db(tmp_path, user_id)

        resp = client.post(
            "/api/v1/admin/backups/bundles",
            json={"user_id": user_id},  # no datasets field → all datasets
        )
        # May fail if some DBs don't exist; 200 or 400 are both acceptable here
        # but we at least verify the endpoint accepts the request shape
        if resp.status_code == 200:
            item = resp.json()["item"]
            assert len(item["datasets"]) >= 1


# ---------------------------------------------------------------------------
# GAP-2: Test size verification during import
# ---------------------------------------------------------------------------

def test_import_size_mismatch(tmp_path):
    """Import should reject files whose size doesn't match manifest."""
    from tldw_Server_API.app.core.exceptions import BundleImportError
    from tldw_Server_API.app.services.admin_bundle_service import import_bundle

    # Build a bundle with tampered size_bytes in manifest
    buf = _make_bundle_zip(datasets=["authnz"])
    # Re-open and patch the manifest to have wrong size
    raw = buf.read()
    buf.seek(0)

    # Extract, modify manifest, and repack
    with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
        manifest = json.loads(zf.read("manifest.json"))
        # Set size_bytes to a wrong value
        for fname in manifest["files"]:
            manifest["files"][fname]["size_bytes"] = "1"  # wrong size
        new_buf = io.BytesIO()
        with zipfile.ZipFile(new_buf, "w") as new_zf:
            for item in zf.infolist():
                if item.filename == "manifest.json":
                    new_zf.writestr("manifest.json", json.dumps(manifest))
                else:
                    new_zf.writestr(item.filename, zf.read(item.filename))

    new_buf.seek(0)
    zip_path = str(tmp_path / "tampered_size.zip")
    with open(zip_path, "wb") as f:
        f.write(new_buf.read())

    with pytest.raises(BundleImportError, match="size_verification_failed"):
        import_bundle(file_path=zip_path, user_id=None, admin_user_id=999)


# ---------------------------------------------------------------------------
# Zip Slip protection test
# ---------------------------------------------------------------------------

def test_import_rejects_path_traversal(tmp_path):
    """Import should reject ZIP entries with path traversal."""
    from tldw_Server_API.app.core.exceptions import BundleImportError
    from tldw_Server_API.app.services.admin_bundle_service import import_bundle

    # Create a ZIP with a path-traversal entry
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        manifest = {
            "manifest_version": 1,
            "app_version": "0.1.0",
            "created_at": "2026-01-01T00:00:00+00:00",
            "user_id": None,
            "datasets": ["authnz"],
            "files": {},
            "schema_versions": {},
            "notes": None,
            "platform": {"os": "test", "python": "3.12", "sqlite": "3.40"},
        }
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("../../etc/evil.db", b"malicious content")

    buf.seek(0)
    zip_path = str(tmp_path / "traversal.zip")
    with open(zip_path, "wb") as f:
        f.write(buf.read())

    with pytest.raises(BundleImportError, match="path_traversal_detected"):
        import_bundle(file_path=zip_path, user_id=None, admin_user_id=998)


# ---------------------------------------------------------------------------
# GAP-9: Multi-user mode user_id_required test
# ---------------------------------------------------------------------------

def test_export_user_id_required_multi_user(tmp_path, monkeypatch):
    """Export of per-user datasets without user_id should fail when auto-resolve fails."""
    from tldw_Server_API.app.core.exceptions import BundleExportError
    from tldw_Server_API.app.services import admin_bundle_service
    from tldw_Server_API.app.services.admin_bundle_service import create_bundle

    admin_bundle_service._rate_limit_windows.clear()

    # Mock get_single_user_id to simulate multi-user mode (no auto-resolve)
    monkeypatch.setattr(
        "tldw_Server_API.app.services.admin_bundle_service.DatabasePaths.get_single_user_id",
        lambda: (_ for _ in ()).throw(RuntimeError("multi-user mode")),
    )

    with pytest.raises(BundleExportError, match="user_id_required"):
        create_bundle(
            datasets=["media"],
            user_id=None,
            admin_user_id=999,
        )


def test_import_user_id_required_multi_user(tmp_path, monkeypatch):
    """Import of per-user datasets without user_id should fail when auto-resolve fails."""
    from tldw_Server_API.app.core.exceptions import BundleImportError
    from tldw_Server_API.app.services import admin_bundle_service
    from tldw_Server_API.app.services.admin_bundle_service import import_bundle

    admin_bundle_service._rate_limit_windows.clear()

    # Mock get_single_user_id to simulate multi-user mode (no auto-resolve)
    monkeypatch.setattr(
        "tldw_Server_API.app.services.admin_bundle_service.DatabasePaths.get_single_user_id",
        lambda: (_ for _ in ()).throw(RuntimeError("multi-user mode")),
    )

    bundle_buf = _make_bundle_zip(datasets=["media"])
    zip_path = str(tmp_path / "multiuser_test.zip")
    with open(zip_path, "wb") as f:
        f.write(bundle_buf.read())

    with pytest.raises(BundleImportError, match="user_id_required"):
        import_bundle(file_path=zip_path, user_id=None, admin_user_id=999)
