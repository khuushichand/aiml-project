from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing import (
    persistence as ingestion_persistence,
)


pytestmark = pytest.mark.unit


class _MetricsCapture:
    def __init__(self) -> None:
        self.increment_calls: list[tuple[str, float, dict[str, Any] | None]] = []

    def increment(
        self,
        metric_name: str,
        value: float = 1,
        labels: dict[str, Any] | None = None,
    ) -> None:
        self.increment_calls.append((metric_name, value, labels))

    def observe(self, *_args: Any, **_kwargs: Any) -> None:
        return None


@pytest.mark.asyncio
async def test_chunk_consistency_warn_policy_adds_warning_and_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _MetricsCapture()
    monkeypatch.setattr(ingestion_persistence, "get_metrics_registry", lambda: metrics)
    monkeypatch.setenv("MEDIA_CHUNK_CONSISTENCY_POLICY", "warn")

    async def _fake_fetch_count(**_kwargs: Any) -> int:
        return 2

    monkeypatch.setattr(
        ingestion_persistence,
        "_fetch_unvectorized_chunk_count",
        _fake_fetch_count,
    )

    result = {
        "status": "Success",
        "warnings": None,
        "error": None,
        "db_id": 11,
        "db_message": "Media 'clip' added.",
        "media_uuid": "uuid-11",
    }
    await ingestion_persistence._enforce_chunk_consistency_after_persist(
        result=result,
        form_data=SimpleNamespace(chunk_consistency_policy=None),
        media_type="audio",
        path_kind="upload",
        processor="audio_primary_persist",
        expected_chunk_count=3,
        db_message=result["db_message"],
        media_id=result["db_id"],
        db_path=":memory:",
        client_id="test-client",
        loop=asyncio.get_running_loop(),
    )

    assert result["status"] == "Success"
    warnings = result.get("warnings") or []
    assert any("Chunk consistency warning" in msg for msg in warnings)
    assert (
        "ingestion_validation_failures_total",
        1,
        {"reason": "chunk_consistency", "path_kind": "upload"},
    ) in metrics.increment_calls


@pytest.mark.asyncio
async def test_chunk_consistency_error_policy_marks_error_but_preserves_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEDIA_CHUNK_CONSISTENCY_POLICY", "error")

    async def _fake_fetch_count(**_kwargs: Any) -> int:
        return 1

    monkeypatch.setattr(
        ingestion_persistence,
        "_fetch_unvectorized_chunk_count",
        _fake_fetch_count,
    )

    result = {
        "status": "Success",
        "warnings": None,
        "error": None,
        "db_id": 22,
        "db_message": "Media 'doc' added.",
        "media_uuid": "uuid-22",
    }
    await ingestion_persistence._enforce_chunk_consistency_after_persist(
        result=result,
        form_data=SimpleNamespace(chunk_consistency_policy=None),
        media_type="document",
        path_kind="url",
        processor="document_persist",
        expected_chunk_count=4,
        db_message=result["db_message"],
        media_id=result["db_id"],
        db_path=":memory:",
        client_id="test-client",
        loop=asyncio.get_running_loop(),
    )

    assert result["status"] == "Error"
    assert "Chunk consistency validation failed" in str(result.get("error", ""))
    assert "Chunk consistency validation failed" in str(result.get("db_message", ""))
    assert result["db_id"] == 22
    assert result["media_uuid"] == "uuid-22"


@pytest.mark.asyncio
async def test_chunk_consistency_skips_non_persisting_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEDIA_CHUNK_CONSISTENCY_POLICY", "warn")

    async def _should_not_run(**_kwargs: Any) -> int:
        raise AssertionError("chunk count lookup should be skipped")

    monkeypatch.setattr(
        ingestion_persistence,
        "_fetch_unvectorized_chunk_count",
        _should_not_run,
    )

    result = {
        "status": "Success",
        "warnings": None,
        "error": None,
        "db_id": 3,
        "db_message": "Media 'x' already exists. Overwrite not enabled.",
        "media_uuid": "uuid-3",
    }
    await ingestion_persistence._enforce_chunk_consistency_after_persist(
        result=result,
        form_data=SimpleNamespace(chunk_consistency_policy=None),
        media_type="audio",
        path_kind="upload",
        processor="audio_primary_persist",
        expected_chunk_count=5,
        db_message=result["db_message"],
        media_id=result["db_id"],
        db_path=":memory:",
        client_id="test-client",
        loop=asyncio.get_running_loop(),
    )

    assert result["status"] == "Success"
    assert result.get("warnings") is None


@pytest.mark.asyncio
async def test_persist_primary_av_item_invokes_chunk_consistency_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int | None] = []

    async def _fake_enforce(**kwargs: Any) -> None:
        calls.append(kwargs.get("expected_chunk_count"))

    async def _fake_persist_claims(**_kwargs: Any) -> None:
        return None

    class _FakeDB:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            return None

        def add_media_with_keywords(self, **_kwargs: Any) -> tuple[int, str, str]:
            return 44, "uuid-44", "Media 'clip' added."

        def close_connection(self) -> None:
            return None

    monkeypatch.setattr(
        ingestion_persistence,
        "_enforce_chunk_consistency_after_persist",
        _fake_enforce,
    )
    monkeypatch.setattr(ingestion_persistence, "persist_claims_if_applicable", _fake_persist_claims)
    monkeypatch.setattr(ingestion_persistence, "MediaDatabase", _FakeDB)

    process_result = {
        "status": "Success",
        "input_ref": "clip.mp3",
        "processing_source": "clip.mp3",
        "metadata": {},
        "content": "hello world. second sentence.",
        "transcript": "hello world. second sentence.",
        "summary": None,
        "analysis": None,
        "analysis_details": {},
        "warnings": None,
        "error": None,
    }

    await ingestion_persistence.persist_primary_av_item(
        process_result=process_result,
        form_data=SimpleNamespace(
            keywords=[],
            custom_prompt=None,
            overwrite_existing=True,
            transcription_model=None,
            chunk_consistency_policy="warn",
        ),
        media_type="audio",
        original_input_ref="clip.mp3",
        chunk_options={"method": "sentences", "max_size": 500, "overlap": 0},
        path_kind="upload",
        db_path=":memory:",
        client_id="test-client",
        loop=asyncio.get_running_loop(),
        claims_context=None,
    )

    assert process_result.get("db_id") == 44
    assert len(calls) == 1
    assert calls[0] is not None
    assert calls[0] > 0
