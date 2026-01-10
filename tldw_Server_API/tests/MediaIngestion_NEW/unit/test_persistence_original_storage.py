from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from fastapi import BackgroundTasks

from tldw_Server_API.app.core.Ingestion_Media_Processing import (
    input_sourcing,
    persistence as ingestion_persistence,
)
from tldw_Server_API.app.api.v1.endpoints import media as media_endpoints
from tldw_Server_API.app.core import Storage
from tldw_Server_API.app.services import storage_quota_service


class _FakeStorage:
    def __init__(self) -> None:
             self.calls: List[Dict[str, Any]] = []

    async def store(
        self,
        *,
        user_id: str,
        media_id: int,
        filename: str,
        data: bytes,
        mime_type: str,
    ) -> str:
        self.calls.append(
            {
                "user_id": user_id,
                "media_id": media_id,
                "filename": filename,
                "data": data,
                "mime_type": mime_type,
            }
        )
        return f"storage/{media_id}/{filename}"


class _FakeDB:
    def __init__(self) -> None:
             self.db_path_str = ":memory:"
        self.client_id = "test-client"
        self.insert_calls: List[Dict[str, Any]] = []

    def insert_media_file(self, **kwargs: Any) -> None:
        self.insert_calls.append(kwargs)


class _FakeQuotaService:
    async def initialize(self) -> None:
        return None

    async def check_quota(
        self,
        user_id: int,
        new_bytes: int,
        raise_on_exceed: bool = False,
    ) -> tuple[bool, Dict[str, Any]]:
        return True, {"current_usage_mb": 0, "new_size_mb": 0, "quota_mb": 1, "available_mb": 1}


@pytest.mark.asyncio
async def test_original_storage_uses_processing_source(monkeypatch):
    storage = _FakeStorage()
    db = _FakeDB()

    async def fake_save_uploaded_files(_files, temp_dir, **_kwargs):
        file_one = Path(temp_dir) / "stored_one.pdf"
        file_two = Path(temp_dir) / "stored_two.pdf"
        file_one.write_bytes(b"file-one")
        file_two.write_bytes(b"file-two")
        saved = [
            {"path": file_one, "original_filename": "duplicate.pdf"},
            {"path": file_two, "original_filename": "duplicate.pdf"},
        ]
        return saved, []

    async def fake_process_doc_item_fn(
        *,
        item_input_ref: str,
        processing_source: str,
        media_type: Any,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        media_id = 1 if "stored_one.pdf" in str(processing_source) else 2
        return {
            "status": "Success",
            "input_ref": item_input_ref,
            "processing_source": str(processing_source),
            "media_type": media_type,
            "metadata": {},
            "content": "content",
            "analysis": None,
            "summary": None,
            "analysis_details": None,
            "db_id": media_id,
            "db_message": "ok",
        }

    monkeypatch.setattr(media_endpoints, "_save_uploaded_files", fake_save_uploaded_files)
    monkeypatch.setattr(media_endpoints, "_process_document_like_item", fake_process_doc_item_fn)
    monkeypatch.setattr(input_sourcing, "save_uploaded_files", fake_save_uploaded_files)
    monkeypatch.setattr(ingestion_persistence, "process_document_like_item", fake_process_doc_item_fn)
    monkeypatch.setattr(Storage, "get_storage_backend", lambda: storage)
    monkeypatch.setattr(storage_quota_service, "StorageQuotaService", _FakeQuotaService)

    form_data = SimpleNamespace(
        media_type="pdf",
        urls=[],
        keep_original_file=True,
        perform_chunking=False,
        perform_analysis=False,
        generate_embeddings=False,
    )

    response = await ingestion_persistence.add_media_orchestrate(
        background_tasks=BackgroundTasks(),
        form_data=form_data,
        files=[object(), object()],
        db=db,
        current_user=SimpleNamespace(id=1),
        usage_log=SimpleNamespace(log_event=lambda *_args, **_kwargs: None),
    )

    assert response.status_code == 200
    stored_payloads = {call["data"] for call in storage.calls}
    assert stored_payloads == {b"file-one", b"file-two"}
    assert len(db.insert_calls) == 2
