from __future__ import annotations

import asyncio
from typing import Any, Dict

import pytest

from tldw_Server_API.app.api.v1.endpoints import media as media_mod
from tldw_Server_API.app.core.Ingestion_Media_Processing import (  # type: ignore
    persistence as core_persistence,
)


@pytest.mark.asyncio()
async def test_document_like_shim_delegates_to_core(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Ensure `endpoints.media._process_document_like_item` delegates into the
    core `persistence.process_document_like_item` helper.
    """

    called: Dict[str, Any] = {}

    async def fake_impl(
        item_input_ref: str,
        processing_source: str,
        media_type: str,
        is_url: bool,
        form_data: Any,
        chunk_options: Any,
        temp_dir: Any,
        loop: Any,
        db_path: str,
        client_id: str,
        user_id: Any = None,
    ) -> Dict[str, Any]:
        # Mark unused parameters as used to satisfy linters without altering behaviour.
        _ = (
            form_data,
            chunk_options,
            temp_dir,
            loop,
            user_id,
        )
        called["args"] = {
            "item_input_ref": item_input_ref,
            "processing_source": processing_source,
            "media_type": media_type,
            "is_url": is_url,
            "db_path": db_path,
            "client_id": client_id,
        }
        return {"status": "Success", "input_ref": item_input_ref}

    monkeypatch.setattr(
        core_persistence,
        "process_document_like_item",
        fake_impl,
        raising=True,
    )

    # Arguments here only need to be structurally valid; the fake
    # implementation will ignore most of them.
    result = await media_mod._process_document_like_item(
        "input-ref",
        "processing-source",
        "document",
        False,
        None,
        {},
        media_mod.CoreTempDirManager().__enter__(),  # type: ignore[call-arg]
        asyncio.get_event_loop(),
        db_path=":memory:",
        client_id="test-client",
        user_id=None,
    )

    assert called, "Expected core persistence.process_document_like_item to be called"
    assert result.get("status") == "Success"
    assert result.get("input_ref") == "input-ref"


def test_process_videos_wrapper_drops_unsupported_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, Any] = {}

    def fake_process_videos(
        *,
        inputs: list[str],
        perform_chunking: bool = True,
    ) -> dict[str, Any]:
        called["inputs"] = inputs
        called["perform_chunking"] = perform_chunking
        return {"status": "ok"}

    monkeypatch.setattr(
        media_mod,
        "_process_videos_core",
        fake_process_videos,
        raising=True,
    )

    result = media_mod.process_videos(
        inputs=["https://example.com/video"],
        perform_chunking=True,
        chunk_options={"method": "sentences", "max_size": 300},
    )

    assert result == {"status": "ok"}
    assert called["inputs"] == ["https://example.com/video"]
    assert called["perform_chunking"] is True


def test_process_audio_wrapper_drops_unsupported_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, Any] = {}

    def fake_process_audio_files(
        *,
        inputs: list[str],
        perform_chunking: bool = True,
    ) -> dict[str, Any]:
        called["inputs"] = inputs
        called["perform_chunking"] = perform_chunking
        return {"status": "ok"}

    monkeypatch.setattr(
        media_mod,
        "_process_audio_files_core",
        fake_process_audio_files,
        raising=True,
    )

    result = media_mod.process_audio_files(
        inputs=["/tmp/audio.wav"],  # nosec B108
        perform_chunking=False,
        chunk_options={"method": "sentences", "max_size": 300},
    )

    assert result == {"status": "ok"}
    assert called["inputs"] == ["/tmp/audio.wav"]  # nosec B108
    assert called["perform_chunking"] is False


def test_keyword_probe_uses_core_for_media_shim_wrapper() -> None:
    def fake_core_video(*, inputs: list[str]) -> dict[str, Any]:
        return {"status": "ok", "inputs": inputs}

    selected = core_persistence._callable_for_keyword_probe(
        candidate_callable=media_mod.process_videos,
        core_fallback=fake_core_video,
    )

    assert selected is fake_core_video
