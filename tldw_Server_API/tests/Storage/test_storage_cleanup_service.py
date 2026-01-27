"""
Tests for storage cleanup service behavior.

Focus on expired-file cleanup:
- Usage decrement via unregister_generated_file
- Safe path resolution prevents traversal deletes
"""
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from tldw_Server_API.app.services import storage_cleanup_service as cleanup


class TestExpiredCleanup:
    """Expired file cleanup tests."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cleanup_expired_calls_unregister_and_deletes_file(self, tmp_path, monkeypatch):
        """Expired files should decrement usage and delete the file when path is safe."""
        # Arrange: create a file under the mocked outputs dir
        file_path = tmp_path / "tts_audio" / "file.txt"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("data")

        files_repo = AsyncMock()
        files_repo.get_expired_files = AsyncMock(return_value=[
            {"id": 1, "user_id": 1, "storage_path": "tts_audio/file.txt"},
        ])

        storage_service = AsyncMock()
        storage_service.unregister_generated_file = AsyncMock(return_value=True)

        monkeypatch.setattr(
            cleanup.DatabasePaths,
            "get_user_outputs_dir",
            lambda user_id: Path(tmp_path),
        )

        # Act
        deleted = await cleanup.cleanup_expired_files(storage_service, files_repo, batch_size=10)

        # Assert
        assert deleted == 1
        storage_service.unregister_generated_file.assert_awaited_once_with(1, hard_delete=True)
        assert not file_path.exists()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cleanup_expired_does_not_delete_unsafe_path(self, tmp_path, monkeypatch):
        """Unsafe paths should be ignored during filesystem deletion."""
        outside_path = tmp_path.parent / "outside.txt"
        outside_path.write_text("data")

        files_repo = AsyncMock()
        files_repo.get_expired_files = AsyncMock(return_value=[
            {"id": 2, "user_id": 1, "storage_path": "../outside.txt"},
        ])

        storage_service = AsyncMock()
        storage_service.unregister_generated_file = AsyncMock(return_value=True)

        monkeypatch.setattr(
            cleanup.DatabasePaths,
            "get_user_outputs_dir",
            lambda user_id: Path(tmp_path),
        )

        deleted = await cleanup.cleanup_expired_files(storage_service, files_repo, batch_size=10)

        assert deleted == 1
        storage_service.unregister_generated_file.assert_awaited_once_with(2, hard_delete=True)
        assert outside_path.exists()
