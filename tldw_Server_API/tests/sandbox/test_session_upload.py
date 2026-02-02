from __future__ import annotations

import io
import os
import tarfile
import zipfile
import tempfile

from fastapi.testclient import TestClient
import pytest

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


def _user(uid: int) -> User:
    return User(id=uid, username=f"user-{uid}", is_active=True, is_admin=False)


def _create_session(client: TestClient) -> str:
    """Helper to create a sandbox session and return its ID."""
    body = {
        "spec_version": "1.0",
        "runtime": "docker",
        "base_image": "python:3.11-slim",
        "timeout_sec": 60,
    }
    r = client.post("/api/v1/sandbox/sessions", json=body)
    assert r.status_code == 200
    return r.json()["id"]


def test_session_upload_creates_workspace(monkeypatch) -> None:
    os.environ.setdefault("TEST_MODE", "1")
    os.environ.setdefault("SANDBOX_ENABLE_EXECUTION", "false")
    os.environ.setdefault("SANDBOX_BACKGROUND_EXECUTION", "true")

    client = TestClient(app)
    app.dependency_overrides[get_request_user] = lambda: _user(1)
    try:
        body = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "timeout_sec": 60,
        }
        r = client.post("/api/v1/sandbox/sessions", json=body)
        assert r.status_code == 200
        session_id = r.json()["id"]

        files = [("files", ("hello.txt", b"hello"))]
        r2 = client.post(f"/api/v1/sandbox/sessions/{session_id}/files", files=files)
        assert r2.status_code == 200
        payload = r2.json()
        assert payload.get("bytes_received") == 5
        assert payload.get("file_count") == 1
    finally:
        app.dependency_overrides.pop(get_request_user, None)


# =============================================================================
# Security Tests: Path Traversal Prevention
# =============================================================================


class TestPathTraversalPrevention:
    """Test cases verifying path traversal attacks are blocked in file uploads."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Set up test environment."""
        os.environ.setdefault("TEST_MODE", "1")
        os.environ.setdefault("SANDBOX_ENABLE_EXECUTION", "false")
        os.environ.setdefault("SANDBOX_BACKGROUND_EXECUTION", "true")

    def test_traversal_filename_dotdot_blocked(self) -> None:
        """Files with ../ in name should be skipped (not cause traversal)."""
        client = TestClient(app)
        app.dependency_overrides[get_request_user] = lambda: _user(1)
        try:
            session_id = _create_session(client)

            # Attempt upload with path traversal in filename
            files = [("files", ("../../../etc/passwd", b"malicious content"))]
            r = client.post(f"/api/v1/sandbox/sessions/{session_id}/files", files=files)
            # Should succeed but skip the malicious file (file_count = 0)
            assert r.status_code == 200
            payload = r.json()
            assert payload.get("file_count") == 0
            assert payload.get("bytes_received") == 0
        finally:
            app.dependency_overrides.pop(get_request_user, None)

    def test_traversal_filename_absolute_path_blocked(self) -> None:
        """Files with absolute paths should be skipped."""
        client = TestClient(app)
        app.dependency_overrides[get_request_user] = lambda: _user(1)
        try:
            session_id = _create_session(client)

            # Attempt upload with absolute path in filename
            files = [("files", ("/etc/passwd", b"malicious content"))]
            r = client.post(f"/api/v1/sandbox/sessions/{session_id}/files", files=files)
            # Should succeed but skip the malicious file
            assert r.status_code == 200
            payload = r.json()
            assert payload.get("file_count") == 0
        finally:
            app.dependency_overrides.pop(get_request_user, None)

    def test_traversal_tar_dotdot_blocked(self) -> None:
        """Tar files containing ../ paths should have those entries skipped."""
        client = TestClient(app)
        app.dependency_overrides[get_request_user] = lambda: _user(1)
        try:
            session_id = _create_session(client)

            # Create a tar file with a path traversal attempt
            tar_buffer = io.BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tf:
                # Add a safe file
                safe_info = tarfile.TarInfo(name="safe.txt")
                safe_content = b"safe content"
                safe_info.size = len(safe_content)
                tf.addfile(safe_info, io.BytesIO(safe_content))

                # Add a malicious file with path traversal
                evil_info = tarfile.TarInfo(name="../../../tmp/evil.txt")
                evil_content = b"evil content"
                evil_info.size = len(evil_content)
                tf.addfile(evil_info, io.BytesIO(evil_content))

            tar_buffer.seek(0)
            files = [("files", ("archive.tar.gz", tar_buffer.read()))]
            r = client.post(f"/api/v1/sandbox/sessions/{session_id}/files", files=files)
            assert r.status_code == 200
            payload = r.json()
            # Only the safe file should be extracted
            assert payload.get("file_count") == 1
        finally:
            app.dependency_overrides.pop(get_request_user, None)

    def test_traversal_tar_symlink_blocked(self) -> None:
        """Symlinks in tar files should be skipped."""
        client = TestClient(app)
        app.dependency_overrides[get_request_user] = lambda: _user(1)
        try:
            session_id = _create_session(client)

            # Create a tar file with a symlink
            tar_buffer = io.BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tf:
                # Add a safe file
                safe_info = tarfile.TarInfo(name="safe.txt")
                safe_content = b"safe content"
                safe_info.size = len(safe_content)
                tf.addfile(safe_info, io.BytesIO(safe_content))

                # Add a symlink to /etc/passwd
                link_info = tarfile.TarInfo(name="evil_link")
                link_info.type = tarfile.SYMTYPE
                link_info.linkname = "/etc/passwd"
                tf.addfile(link_info)

            tar_buffer.seek(0)
            files = [("files", ("archive.tar.gz", tar_buffer.read()))]
            r = client.post(f"/api/v1/sandbox/sessions/{session_id}/files", files=files)
            assert r.status_code == 200
            payload = r.json()
            # Only the safe file should be extracted, symlink should be skipped
            assert payload.get("file_count") == 1
        finally:
            app.dependency_overrides.pop(get_request_user, None)

    def test_traversal_zip_dotdot_blocked(self) -> None:
        """Zip files containing ../ paths should have those entries skipped."""
        client = TestClient(app)
        app.dependency_overrides[get_request_user] = lambda: _user(1)
        try:
            session_id = _create_session(client)

            # Create a zip file with a path traversal attempt
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                # Add a safe file
                zf.writestr("safe.txt", "safe content")
                # Add a malicious file with path traversal
                zf.writestr("../../../tmp/evil.txt", "evil content")

            zip_buffer.seek(0)
            files = [("files", ("archive.zip", zip_buffer.read()))]
            r = client.post(f"/api/v1/sandbox/sessions/{session_id}/files", files=files)
            assert r.status_code == 200
            payload = r.json()
            # Only the safe file should be extracted
            assert payload.get("file_count") == 1
        finally:
            app.dependency_overrides.pop(get_request_user, None)

    def test_traversal_zip_symlink_blocked(self) -> None:
        """Symlinks in zip files should be skipped.

        Zip files can represent symlinks via the external_attr field.
        The Unix symlink mode 0o120000 is stored in the high 16 bits.
        """
        client = TestClient(app)
        app.dependency_overrides[get_request_user] = lambda: _user(1)
        try:
            session_id = _create_session(client)

            # Create a zip file with a symlink
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                # Add a safe file
                zf.writestr("safe.txt", "safe content")

                # Add a symlink entry
                # Unix symlink mode is 0o120000, stored in high 16 bits of external_attr
                symlink_info = zipfile.ZipInfo("evil_symlink")
                # Set symlink mode: 0o120777 (symlink with all perms) in high 16 bits
                symlink_info.external_attr = (0o120777 << 16)
                zf.writestr(symlink_info, "/etc/passwd")

            zip_buffer.seek(0)
            files = [("files", ("archive.zip", zip_buffer.read()))]
            r = client.post(f"/api/v1/sandbox/sessions/{session_id}/files", files=files)
            assert r.status_code == 200
            payload = r.json()
            # Only the safe file should be extracted, symlink should be skipped
            assert payload.get("file_count") == 1
        finally:
            app.dependency_overrides.pop(get_request_user, None)

    def test_safe_join_rejects_prefix_confusion(self) -> None:
        """Test that safe_join properly rejects prefix confusion attacks.

        A prefix confusion attack happens when:
        - base_dir = '/sandbox/user1'
        - name results in '/sandbox/user1_evil/file.txt'
        - A naive startswith() check would pass this
        """
        from tldw_Server_API.app.core.Utils.path_utils import safe_join

        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, "user1")
            os.makedirs(base)

            # Create a sibling directory that shares the prefix
            evil_sibling = os.path.join(tmpdir, "user1_evil")
            os.makedirs(evil_sibling)

            # Attempt to escape to sibling via traversal
            # This simulates: /sandbox/user1 + ../user1_evil/pwned.txt
            result = safe_join(base, "../user1_evil/pwned.txt")
            assert result is None, "safe_join should reject prefix confusion attacks"

    def test_safe_join_rejects_symlink_escape(self) -> None:
        """Test that safe_join rejects paths that resolve through symlinks."""
        from tldw_Server_API.app.core.Utils.path_utils import safe_join

        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, "workspace")
            os.makedirs(base)

            # Create target directory outside workspace
            target = os.path.join(tmpdir, "outside")
            os.makedirs(target)

            # Create a symlink inside workspace pointing outside
            symlink = os.path.join(base, "escape")
            os.symlink(target, symlink)

            # Attempt to access file through symlink
            result = safe_join(base, "escape/secret.txt")
            assert result is None, "safe_join should reject symlink escapes"

    def test_multiple_traversal_patterns(self) -> None:
        """Test various path traversal patterns are all blocked."""
        client = TestClient(app)
        app.dependency_overrides[get_request_user] = lambda: _user(1)
        try:
            session_id = _create_session(client)

            # These traversal patterns use forward slashes which work on all platforms
            traversal_patterns = [
                "../secret.txt",
                "foo/../../../secret.txt",
                "foo/bar/../../../../../../etc/passwd",
                "./../secret.txt",
            ]

            for pattern in traversal_patterns:
                files = [("files", (pattern, b"test content"))]
                r = client.post(f"/api/v1/sandbox/sessions/{session_id}/files", files=files)
                assert r.status_code == 200
                payload = r.json()
                # All traversal attempts should be blocked
                assert payload.get("file_count") == 0, f"Pattern {pattern!r} should be blocked"
        finally:
            app.dependency_overrides.pop(get_request_user, None)

    def test_windows_style_traversal_blocked_on_windows(self) -> None:
        """Test that Windows-style backslash traversal is blocked.

        Note: On Unix systems, backslashes are valid filename characters,
        so this test verifies proper handling on the current platform.
        """
        import sys

        client = TestClient(app)
        app.dependency_overrides[get_request_user] = lambda: _user(1)
        try:
            session_id = _create_session(client)

            # Windows-style traversal pattern
            pattern = "..\\secret.txt"
            files = [("files", (pattern, b"test content"))]
            r = client.post(f"/api/v1/sandbox/sessions/{session_id}/files", files=files)
            assert r.status_code == 200
            payload = r.json()

            if sys.platform == "win32":
                # On Windows, backslash is a path separator, so this should be blocked
                assert payload.get("file_count") == 0, "Windows traversal should be blocked on Windows"
            else:
                # On Unix, backslash is a valid filename character
                # The file is written with the literal name "..\\secret.txt"
                # which is safe (doesn't traverse) but allowed
                pass  # Either outcome is acceptable on Unix
        finally:
            app.dependency_overrides.pop(get_request_user, None)
