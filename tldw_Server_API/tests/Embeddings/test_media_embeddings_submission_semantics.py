import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.endpoints import media_embeddings
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User


class _FakeMediaDB:
    def __init__(self, media_ids: list[int]):
        self._ids = set(int(media_id) for media_id in media_ids)

    def get_media_by_id(self, media_id: int, **_kwargs):
        if int(media_id) in self._ids:
            return {"id": int(media_id), "title": "Doc", "author": "A"}
        return None


def _user() -> User:
    return User(id="user-1", username="user-1", email="user-1@example.com", is_active=True, is_admin=True)


@pytest.mark.asyncio
async def test_generate_embeddings_fails_when_job_create_raises(monkeypatch):
    class _FailingAdapter:
        def create_job(self, **_kwargs):
            raise RuntimeError("queue unavailable")

    monkeypatch.setattr(media_embeddings, "_embeddings_jobs_backend", lambda: "jobs")
    monkeypatch.setattr(media_embeddings, "_resolve_model_provider", lambda *_: ("model-a", "provider-a"))
    monkeypatch.setattr(media_embeddings, "EmbeddingsJobsAdapter", _FailingAdapter)

    with pytest.raises(HTTPException) as excinfo:
        await media_embeddings.generate_embeddings(
            media_id=123,
            request=media_embeddings.GenerateEmbeddingsRequest(),
            db=_FakeMediaDB([123]),
            current_user=_user(),
        )

    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "Failed to queue embedding job"


@pytest.mark.asyncio
async def test_generate_embeddings_fails_when_job_id_missing(monkeypatch):
    class _MissingIdAdapter:
        def create_job(self, **_kwargs):
            return {}

    monkeypatch.setattr(media_embeddings, "_embeddings_jobs_backend", lambda: "jobs")
    monkeypatch.setattr(media_embeddings, "_resolve_model_provider", lambda *_: ("model-a", "provider-a"))
    monkeypatch.setattr(media_embeddings, "EmbeddingsJobsAdapter", _MissingIdAdapter)

    with pytest.raises(HTTPException) as excinfo:
        await media_embeddings.generate_embeddings(
            media_id=123,
            request=media_embeddings.GenerateEmbeddingsRequest(),
            db=_FakeMediaDB([123]),
            current_user=_user(),
        )

    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "Failed to queue embedding job"


@pytest.mark.asyncio
async def test_generate_embeddings_batch_returns_partial_response_on_partial_enqueue_error(monkeypatch):
    class _PartialAdapter:
        def create_job(self, **kwargs):
            media_id = int(kwargs["media_id"])
            if media_id == 456:
                raise RuntimeError("enqueue failed")
            return {"uuid": f"job-{media_id}"}

    monkeypatch.setattr(media_embeddings, "_embeddings_jobs_backend", lambda: "jobs")
    monkeypatch.setattr(media_embeddings, "_resolve_model_provider", lambda *_: ("model-a", "provider-a"))
    monkeypatch.setattr(media_embeddings, "EmbeddingsJobsAdapter", _PartialAdapter)

    response = await media_embeddings.generate_embeddings_batch(
        request=media_embeddings.BatchMediaEmbeddingsRequest(media_ids=[123, 456]),
        db=_FakeMediaDB([123, 456]),
        current_user=_user(),
    )

    assert response.status == "partial"
    assert response.job_ids == ["job-123"]
    assert response.submitted == 1
    assert response.failed_media_ids == [456]
    assert response.failure_reasons == ["media_id=456: RuntimeError"]


@pytest.mark.asyncio
async def test_generate_embeddings_batch_raises_when_all_enqueues_fail_before_any_success(monkeypatch):
    class _AlwaysFailingAdapter:
        def create_job(self, **kwargs):
            raise RuntimeError("enqueue failed")

    monkeypatch.setattr(media_embeddings, "_embeddings_jobs_backend", lambda: "jobs")
    monkeypatch.setattr(media_embeddings, "_resolve_model_provider", lambda *_: ("model-a", "provider-a"))
    monkeypatch.setattr(media_embeddings, "EmbeddingsJobsAdapter", _AlwaysFailingAdapter)

    with pytest.raises(HTTPException) as excinfo:
        await media_embeddings.generate_embeddings_batch(
            request=media_embeddings.BatchMediaEmbeddingsRequest(media_ids=[456]),
            db=_FakeMediaDB([456]),
            current_user=_user(),
        )

    assert excinfo.value.status_code == 500
    assert isinstance(excinfo.value.detail, dict)
    assert excinfo.value.detail.get("error") == "batch_enqueue_failed"
    assert excinfo.value.detail.get("submitted") == 0
    assert excinfo.value.detail.get("failed_media_ids") == [456]
