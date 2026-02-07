from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from fastapi import BackgroundTasks
from fastapi import status

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
        payload = data
        if hasattr(data, "read") and not isinstance(data, (bytes, bytearray)):
            payload = data.read()
            if hasattr(data, "seek"):
                data.seek(0)
        if isinstance(payload, bytearray):
            payload = bytes(payload)
        self.calls.append(
            {
                "user_id": user_id,
                "media_id": media_id,
                "filename": filename,
                "data": payload,
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


@pytest.fixture
def fake_storage() -> _FakeStorage:
    return _FakeStorage()


@pytest.fixture
def fake_db() -> _FakeDB:
    return _FakeDB()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_original_storage_uses_processing_source(monkeypatch, fake_db, fake_storage):
    storage = fake_storage
    db = fake_db

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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_media_orchestrate_handles_document_exceptions(monkeypatch, tmp_path, fake_db, fake_storage):
    db = fake_db

    async def fake_save_uploaded_files(_files, temp_dir, **_kwargs):
        ok_path = Path(temp_dir) / "ok.txt"
        ok_path.write_text("ok")
        return [{"path": ok_path, "original_filename": "ok.txt"}], []

    async def fake_process_doc_item_fn(
        *,
        item_input_ref: str,
        processing_source: str,
        media_type: Any,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        if str(processing_source).startswith("https://fail.test"):
            raise RuntimeError("boom")
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
            "db_id": 1,
            "db_message": "ok",
        }

    monkeypatch.setattr(media_endpoints, "_save_uploaded_files", fake_save_uploaded_files)
    monkeypatch.setattr(media_endpoints, "_process_document_like_item", fake_process_doc_item_fn)
    monkeypatch.setattr(input_sourcing, "save_uploaded_files", fake_save_uploaded_files)
    monkeypatch.setattr(ingestion_persistence, "process_document_like_item", fake_process_doc_item_fn)

    form_data = SimpleNamespace(
        media_type="document",
        urls=["https://fail.test/doc"],
        keep_original_file=False,
        perform_chunking=False,
        perform_analysis=False,
        generate_embeddings=False,
    )

    response = await ingestion_persistence.add_media_orchestrate(
        background_tasks=BackgroundTasks(),
        form_data=form_data,
        files=[object()],
        db=db,
        current_user=SimpleNamespace(id=1),
        usage_log=SimpleNamespace(log_event=lambda *_args, **_kwargs: None),
    )

    assert response.status_code == status.HTTP_207_MULTI_STATUS
    body = json.loads(response.body)
    results = body.get("results") or []

    assert any(
        result.get("status") == "Error"
        and result.get("input_ref") == "https://fail.test/doc"
        for result in results
    )
    assert any(
        result.get("status") == "Success" and result.get("input_ref") == "ok.txt"
        for result in results
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_media_orchestrate_partial_upload_errors_returns_multi_status(monkeypatch, fake_db, fake_storage):
    db = fake_db

    async def fake_save_uploaded_files(_files, temp_dir, **_kwargs):
        ok_path = Path(temp_dir) / "ok.pdf"
        ok_path.write_bytes(b"ok")
        return (
            [{"path": ok_path, "original_filename": "ok.pdf"}],
            [
                {
                    "original_filename": "bad.exe",
                    "input_ref": "bad.exe",
                    "status": "Error",
                    "error": "File type '.exe' is not allowed for security reasons",
                }
            ],
        )

    async def fake_process_doc_item_fn(
        *,
        item_input_ref: str,
        processing_source: str,
        media_type: Any,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
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
            "db_id": 1,
            "db_message": "ok",
        }

    monkeypatch.setattr(media_endpoints, "_save_uploaded_files", fake_save_uploaded_files)
    monkeypatch.setattr(media_endpoints, "_process_document_like_item", fake_process_doc_item_fn)
    monkeypatch.setattr(input_sourcing, "save_uploaded_files", fake_save_uploaded_files)
    monkeypatch.setattr(ingestion_persistence, "process_document_like_item", fake_process_doc_item_fn)

    form_data = SimpleNamespace(
        media_type="pdf",
        urls=[],
        keep_original_file=False,
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

    assert response.status_code == status.HTTP_207_MULTI_STATUS
    body = json.loads(response.body)
    results = body.get("results") or []
    assert any(r.get("status") == "Error" and r.get("input_ref") == "bad.exe" for r in results)
    assert any(r.get("status") == "Success" and r.get("input_ref") == "ok.pdf" for r in results)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_media_orchestrate_document_concurrency_limit(monkeypatch, fake_db, fake_storage):
    db = fake_db
    monkeypatch.setenv("DOCUMENT_LIKE_CONCURRENCY", "2")

    async def fake_save_uploaded_files(_files, temp_dir, **_kwargs):
        saved = []
        for idx in range(5):
            path = Path(temp_dir) / f"doc_{idx}.txt"
            path.write_text("ok")
            saved.append({"path": path, "original_filename": f"doc_{idx}.txt"})
        return saved, []

    state = {"current": 0, "max": 0}
    lock = asyncio.Lock()

    async def fake_process_doc_item_fn(
        *,
        item_input_ref: str,
        processing_source: str,
        media_type: Any,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        async with lock:
            state["current"] += 1
            state["max"] = max(state["max"], state["current"])
        await asyncio.sleep(0.05)
        async with lock:
            state["current"] -= 1
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
            "db_id": 1,
            "db_message": "ok",
        }

    monkeypatch.setattr(media_endpoints, "_save_uploaded_files", fake_save_uploaded_files)
    monkeypatch.setattr(media_endpoints, "_process_document_like_item", fake_process_doc_item_fn)
    monkeypatch.setattr(input_sourcing, "save_uploaded_files", fake_save_uploaded_files)
    monkeypatch.setattr(ingestion_persistence, "process_document_like_item", fake_process_doc_item_fn)

    form_data = SimpleNamespace(
        media_type="document",
        urls=[],
        keep_original_file=False,
        perform_chunking=False,
        perform_analysis=False,
        generate_embeddings=False,
    )

    response = await ingestion_persistence.add_media_orchestrate(
        background_tasks=BackgroundTasks(),
        form_data=form_data,
        files=[object() for _ in range(5)],
        db=db,
        current_user=SimpleNamespace(id=1),
        usage_log=SimpleNamespace(log_event=lambda *_args, **_kwargs: None),
    )

    assert response.status_code == status.HTTP_200_OK
    assert state["max"] <= 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_batch_media_test_mode_accepts_single_letter_y(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TEST_MODE", "y")
    monkeypatch.delenv("TESTING", raising=False)

    captured: dict[str, Any] = {}

    def _fake_evaluate_url_policy(url: str, block_private_override: bool | None = None):
        captured["url"] = url
        captured["block_private_override"] = block_private_override
        return SimpleNamespace(allowed=False, reason="blocked-for-test")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Security.egress.evaluate_url_policy",
        _fake_evaluate_url_policy,
        raising=True,
    )

    url = "https://example.com/demo.mp3"
    results = await ingestion_persistence.process_batch_media(
        media_type="audio",
        urls=[url],
        uploaded_file_paths=[],
        source_to_ref_map={url: url},
        form_data=SimpleNamespace(overwrite_existing=False, transcription_model=None),
        chunk_options=None,
        loop=asyncio.get_running_loop(),
        db_path=str(tmp_path / "media.db"),
        client_id="test-client",
        temp_dir=tmp_path,
    )

    assert captured.get("url") == url
    assert captured.get("block_private_override") is False
    assert len(results) == 1
    assert "URL blocked by security policy" in str(results[0].get("error"))
