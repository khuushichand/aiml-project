from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing import persistence
import tldw_Server_API.app.core.Embeddings.jobs_adapter as jobs_adapter_module


pytestmark = pytest.mark.unit


class _FakeBackgroundTasks:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    def add_task(self, func: Any, *args: Any, **kwargs: Any) -> None:
        self.calls.append((func, args, kwargs))


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
async def test_schedule_media_add_embeddings_jobs_mode_passes_provenance(monkeypatch):
    monkeypatch.setenv("MEDIA_ADD_EMBEDDINGS_MODE", "jobs")
    captured: dict[str, Any] = {}
    metrics = _MetricsCapture()

    class _FakeAdapter:
        def create_job(self, **kwargs: Any) -> dict[str, Any]:
            captured["kwargs"] = kwargs
            return {"uuid": "job-media-add-1"}

    monkeypatch.setattr(
        jobs_adapter_module,
        "EmbeddingsJobsAdapter",
        _FakeAdapter,
    )
    monkeypatch.setattr(persistence, "get_metrics_registry", lambda: metrics)

    results = [
        {
            "status": "Success",
            "db_id": 314,
            "media_type": "document",
            "media_uuid": "uuid-314",
            "input_ref": "https://example.org/item",
            "processing_source": "https://example.org/item",
            "collections_origin": "media_add",
            "collections_item_id": 999,
        }
    ]

    tasks = _FakeBackgroundTasks()
    await persistence.schedule_media_add_embeddings(
        results=results,
        form_data=SimpleNamespace(
            generate_embeddings=True,
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            embedding_provider="huggingface",
            chunk_size=123,
            chunk_overlap=17,
            media_type="document",
        ),
        background_tasks=tasks,  # type: ignore[arg-type]
        db=SimpleNamespace(),
        current_user=SimpleNamespace(id=77),
    )

    assert len(tasks.calls) == 0
    assert results[0]["embeddings_scheduled"] is True
    assert results[0]["embeddings_dispatch"] == "jobs"
    assert results[0]["embeddings_job_id"] == "job-media-add-1"

    job_kwargs = captured["kwargs"]
    assert job_kwargs["user_id"] == "77"
    assert job_kwargs["media_id"] == 314
    assert job_kwargs["request_source"] == "media_add"
    assert job_kwargs["chunk_size"] == 123
    assert job_kwargs["chunk_overlap"] == 17

    provenance = job_kwargs["provenance"]
    assert provenance["origin"] == "media_add"
    assert provenance["media_id"] == 314
    assert provenance["source_id"] == 314
    assert provenance["run_id"] is None
    assert provenance["job_id"] is None
    assert provenance["collections_item_id"] == 999
    assert provenance["entrypoint"] == "/api/v1/media/add"
    assert (
        "ingestion_embeddings_enqueue_total",
        1,
        {"path_kind": "jobs", "outcome": "success"},
    ) in metrics.increment_calls


@pytest.mark.asyncio
async def test_schedule_media_add_embeddings_background_mode_adds_task(monkeypatch):
    monkeypatch.setenv("MEDIA_ADD_EMBEDDINGS_MODE", "background")
    tasks = _FakeBackgroundTasks()

    results = [
        {
            "status": "Success",
            "db_id": 88,
            "media_type": "document",
            "input_ref": "background.txt",
            "processing_source": "/tmp/background.txt",
        }
    ]

    await persistence.schedule_media_add_embeddings(
        results=results,
        form_data=SimpleNamespace(
            generate_embeddings=True,
            embedding_model=None,
            embedding_provider=None,
            chunk_size=64,
            chunk_overlap=16,
            media_type="document",
        ),
        background_tasks=tasks,  # type: ignore[arg-type]
        db=SimpleNamespace(),
        current_user=SimpleNamespace(id=11),
    )

    assert len(tasks.calls) == 1
    _func, args, kwargs = tasks.calls[0]
    assert kwargs == {}
    assert args[0] == 88
    assert isinstance(args[1], dict)
    assert args[1]["media_id"] == 88
    assert args[1]["source_id"] == 88
    assert args[1]["origin"] == "media_add"
    assert results[0]["embeddings_scheduled"] is True
    assert results[0]["embeddings_dispatch"] == "background"
    assert "embeddings_job_id" not in results[0]


@pytest.mark.asyncio
async def test_schedule_media_add_embeddings_auto_falls_back_to_background(monkeypatch):
    monkeypatch.setenv("MEDIA_ADD_EMBEDDINGS_MODE", "auto")
    tasks = _FakeBackgroundTasks()
    metrics = _MetricsCapture()

    class _FailingAdapter:
        def create_job(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ARG002 - exercised by call
            raise RuntimeError("queue unavailable")

    monkeypatch.setattr(
        jobs_adapter_module,
        "EmbeddingsJobsAdapter",
        _FailingAdapter,
    )
    monkeypatch.setattr(persistence, "get_metrics_registry", lambda: metrics)

    results = [
        {
            "status": "Success",
            "db_id": 101,
            "media_type": "document",
            "input_ref": "https://example.org/auto-fallback",
            "processing_source": "https://example.org/auto-fallback",
        }
    ]

    await persistence.schedule_media_add_embeddings(
        results=results,
        form_data=SimpleNamespace(
            generate_embeddings=True,
            embedding_model="model-a",
            embedding_provider="provider-a",
            chunk_size=100,
            chunk_overlap=20,
            media_type="document",
        ),
        background_tasks=tasks,  # type: ignore[arg-type]
        db=SimpleNamespace(),
        current_user=SimpleNamespace(id=9),
    )

    assert len(tasks.calls) == 1
    assert results[0]["embeddings_scheduled"] is True
    assert results[0]["embeddings_dispatch"] == "background"
    warnings = results[0].get("warnings") or []
    assert any("Embeddings jobs enqueue failed" in warning for warning in warnings)
    assert (
        "ingestion_embeddings_enqueue_total",
        1,
        {"path_kind": "jobs", "outcome": "failure"},
    ) in metrics.increment_calls
    assert (
        "ingestion_embeddings_enqueue_total",
        1,
        {"path_kind": "background", "outcome": "success"},
    ) in metrics.increment_calls
