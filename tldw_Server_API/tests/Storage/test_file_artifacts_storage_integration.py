"""
Tests for FileArtifactsService integration with generated files storage.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from tldw_Server_API.app.core.File_Artifacts.file_artifacts_service import FileArtifactsService
from tldw_Server_API.app.core.exceptions import FileArtifactsError
from tldw_Server_API.app.core.AuthNZ.exceptions import QuotaExceededError
from tldw_Server_API.app.core.File_Artifacts import file_artifacts_service as service_module


@pytest.mark.unit
@pytest.mark.asyncio
async def test_register_generated_file_export_image(monkeypatch):
    """Image exports register generated files."""
    service = FileArtifactsService(MagicMock(), user_id=1)
    save_image = AsyncMock()
    monkeypatch.setattr(service_module, "save_and_register_image", save_image)

    await service._register_generated_file_export(
        file_id=10,
        file_type="image",
        export_format="png",
        content=b"image-bytes",
    )

    assert save_image.await_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_register_generated_file_export_spreadsheet(monkeypatch):
    """Spreadsheet exports register generated files."""
    service = FileArtifactsService(MagicMock(), user_id=1)
    save_sheet = AsyncMock()
    monkeypatch.setattr(service_module, "save_and_register_spreadsheet", save_sheet)

    await service._register_generated_file_export(
        file_id=11,
        file_type="data_table",
        export_format="xlsx",
        content=b"xlsx-bytes",
    )

    assert save_sheet.await_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_register_generated_file_export_maps_quota_error(monkeypatch):
    """QuotaExceededError is surfaced as FileArtifactsError."""
    service = FileArtifactsService(MagicMock(), user_id=1)
    save_image = AsyncMock(side_effect=QuotaExceededError(20.0, 10))
    monkeypatch.setattr(service_module, "save_and_register_image", save_image)

    with pytest.raises(FileArtifactsError) as exc:
        await service._register_generated_file_export(
            file_id=12,
            file_type="image",
            export_format="png",
            content=b"image-bytes",
        )

    assert exc.value.code == "storage_quota_exceeded"
