from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


def _set_jobs_db(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.delenv("JOBS_DB_URL", raising=False)
    monkeypatch.setenv("MEDIA_INGEST_JOBS_ROUTE_HEAVY", "false")


def _allow_url_policy(monkeypatch) -> None:
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Security.egress.evaluate_url_policy",
        lambda *_args, **_kwargs: SimpleNamespace(allowed=True, reason=None),
        raising=True,
    )


@pytest.mark.asyncio
async def test_media_ingest_job_completion_exposes_reserved_video_lite_summary_metadata(
    auth_headers,
    media_database,
    monkeypatch,
    tmp_path,
):
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
    from tldw_Server_API.app.core.Jobs.manager import JobManager
    from tldw_Server_API.app.main import app
    import tldw_Server_API.app.services.media_ingest_jobs_worker as worker

    _set_jobs_db(monkeypatch, tmp_path)
    _allow_url_policy(monkeypatch)
    monkeypatch.setenv("PRIVILEGE_METADATA_VALIDATE_ON_STARTUP", "0")

    source_url = "https://www.youtube.com/watch?v=summary123"
    processor_calls: list[str] = []

    async def _fake_process_videos(**kwargs):
        processor_calls.extend(kwargs.get("inputs") or [])
        return {
            "results": [
                {
                    "status": "Success",
                    "input_ref": source_url,
                    "processing_source": source_url,
                    "media_type": "video",
                    "transcript": "Transcript content for the test video.",
                    "segments": [],
                    "summary": "A reserved summary for the test video.",
                    "analysis": "Generic analysis should not be used by lite.",
                    "analysis_details": {"transcription_language": "en"},
                    "metadata": {
                        "title": "Reserved Summary Video",
                        "author": "Test Author",
                        "source_url": source_url,
                        "url": source_url,
                        "model": "whisper-test",
                        "provider": "whisper",
                        "source": "youtube",
                    },
                    "warnings": None,
                }
            ],
            "errors_count": 0,
            "errors": [],
        }

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib.process_videos",
        _fake_process_videos,
        raising=True,
    )

    def _override_media_db():
        return media_database

    def _worker_db_factory(_user_id: str):
        db = MediaDatabase(db_path=media_database.db_path_str, client_id="1")
        db.initialize_db()
        return db

    with TestClient(app) as test_client:
        app.dependency_overrides[get_media_db_for_user] = _override_media_db
        monkeypatch.setattr(worker, "_create_db", _worker_db_factory, raising=True)
        try:
            submit_resp = test_client.post(
                "/api/v1/media/ingest/jobs",
                data={
                    "media_type": "video",
                    "urls": source_url,
                    "transcription_model": "whisper-test",
                },
                headers=auth_headers,
            )
            assert submit_resp.status_code == 200, submit_resp.text
            job_id = int(submit_resp.json()["jobs"][0]["id"])

            jm = JobManager()
            queued_job = jm.get_job(job_id)
            assert queued_job is not None
            acquired_job = jm.acquire_next_job(
                domain="media_ingest",
                queue=str(queued_job.get("queue") or "default"),
                lease_seconds=120,
                worker_id="test-worker",
            )
            assert acquired_job is not None

            result = await worker._handle_job(acquired_job, jm, worker._ProgressState())
            completed = jm.complete_job(
                job_id,
                result=result,
                worker_id="test-worker",
                lease_id=str(acquired_job.get("lease_id")),
                enforce=False,
            )
            assert completed is True

            status_resp = test_client.get(
                f"/api/v1/media/ingest/jobs/{job_id}",
                headers=auth_headers,
            )
            assert status_resp.status_code == 200, status_resp.text
            status_body = status_resp.json()
            assert status_body["status"] == "completed"
            assert status_body["result"]["media_id"]

            media_id = int(status_body["result"]["media_id"])
            detail_resp = test_client.get(f"/api/v1/media/{media_id}", headers=auth_headers)
            assert detail_resp.status_code == 200, detail_resp.text
            detail = detail_resp.json()
            assert detail["content"]["text"] == "Transcript content for the test video."
            assert detail["processing"]["safe_metadata"]["video_lite"]["summary"] == (
                "A reserved summary for the test video."
            )
            assert detail["processing"]["safe_metadata"]["video_lite"]["summary_status"] == "ready"
            assert processor_calls == [source_url]
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_media_ingest_job_second_submit_reuses_existing_media_id_without_reprocessing(
    auth_headers,
    media_database,
    monkeypatch,
    tmp_path,
):
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
    from tldw_Server_API.app.core.Jobs.manager import JobManager
    from tldw_Server_API.app.main import app
    import tldw_Server_API.app.services.media_ingest_jobs_worker as worker

    _set_jobs_db(monkeypatch, tmp_path)
    _allow_url_policy(monkeypatch)
    monkeypatch.setenv("PRIVILEGE_METADATA_VALIDATE_ON_STARTUP", "0")

    source_url = "https://www.youtube.com/watch?v=dedupe123"
    processor_calls: list[str] = []

    async def _fake_process_videos(**kwargs):
        processor_calls.extend(kwargs.get("inputs") or [])
        return {
            "results": [
                {
                    "status": "Success",
                    "input_ref": source_url,
                    "processing_source": source_url,
                    "media_type": "video",
                    "transcript": "Reusable transcript.",
                    "segments": [],
                    "summary": "Reusable summary.",
                    "analysis_details": {"transcription_language": "en"},
                    "metadata": {
                        "title": "Reusable Video",
                        "author": "Test Author",
                        "source_url": source_url,
                        "url": source_url,
                        "model": "whisper-test",
                        "provider": "whisper",
                    },
                    "warnings": None,
                }
            ],
            "errors_count": 0,
            "errors": [],
        }

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib.process_videos",
        _fake_process_videos,
        raising=True,
    )

    def _override_media_db():
        return media_database

    def _worker_db_factory(_user_id: str):
        db = MediaDatabase(db_path=media_database.db_path_str, client_id="1")
        db.initialize_db()
        return db

    with TestClient(app) as test_client:
        app.dependency_overrides[get_media_db_for_user] = _override_media_db
        monkeypatch.setattr(worker, "_create_db", _worker_db_factory, raising=True)
        try:
            job_manager = JobManager()
            media_ids: list[int] = []

            for _ in range(2):
                submit_resp = test_client.post(
                    "/api/v1/media/ingest/jobs",
                    data={
                        "media_type": "video",
                        "urls": source_url,
                        "transcription_model": "whisper-test",
                    },
                    headers=auth_headers,
                )
                assert submit_resp.status_code == 200, submit_resp.text
                job_id = int(submit_resp.json()["jobs"][0]["id"])

                queued_job = job_manager.get_job(job_id)
                assert queued_job is not None
                acquired_job = job_manager.acquire_next_job(
                    domain="media_ingest",
                    queue=str(queued_job.get("queue") or "default"),
                    lease_seconds=120,
                    worker_id=f"test-worker-{job_id}",
                )
                assert acquired_job is not None
                result = await worker._handle_job(acquired_job, job_manager, worker._ProgressState())
                completed = job_manager.complete_job(
                    job_id,
                    result=result,
                    worker_id=f"test-worker-{job_id}",
                    lease_id=str(acquired_job.get("lease_id")),
                    enforce=False,
                )
                assert completed is True
                media_ids.append(int(result["media_id"]))

            assert media_ids[0] == media_ids[1]
            assert processor_calls == [source_url]
        finally:
            app.dependency_overrides.clear()
