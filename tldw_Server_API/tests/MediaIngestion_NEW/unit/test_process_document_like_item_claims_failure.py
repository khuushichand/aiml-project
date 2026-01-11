from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing import persistence
from tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext import Plaintext_Files


@pytest.mark.asyncio
async def test_process_document_like_item_claims_failure_adds_warning(tmp_path, monkeypatch):
    def fake_process_document_content(**_kwargs: Any) -> Dict[str, Any]:
        return {
            "status": "Success",
            "content": "ok",
            "metadata": {},
            "analysis": None,
            "summary": None,
            "analysis_details": {},
            "error": None,
            "warnings": None,
        }

    async def fake_persist_doc_item_and_children(**_kwargs: Any) -> None:
        return None

    async def fake_extract_claims_if_requested(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("claims boom")

    monkeypatch.setattr(
        Plaintext_Files,
        "process_document_content",
        fake_process_document_content,
    )
    monkeypatch.setattr(
        persistence,
        "persist_doc_item_and_children",
        fake_persist_doc_item_and_children,
    )
    monkeypatch.setattr(
        persistence,
        "extract_claims_if_requested",
        fake_extract_claims_if_requested,
    )

    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("hello")

    form_data = SimpleNamespace(
        title=None,
        author=None,
        keywords=None,
        perform_chunking=False,
        perform_analysis=False,
        api_name=None,
        custom_prompt=None,
        system_prompt=None,
        summarize_recursively=False,
    )

    result = await persistence.process_document_like_item(
        item_input_ref="doc.txt",
        processing_source=str(doc_path),
        media_type="document",
        is_url=False,
        form_data=form_data,
        chunk_options=None,
        temp_dir=tmp_path,
        loop=asyncio.get_running_loop(),
        db_path=":memory:",
        client_id="test-client",
        user_id=None,
    )

    assert result.get("status") == "Success"
    warnings = result.get("warnings") or []
    assert any("Claim extraction failed" in warning for warning in warnings)
