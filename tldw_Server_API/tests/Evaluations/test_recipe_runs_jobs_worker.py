from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import RunStatus
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_single_user_instance
from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase
from tldw_Server_API.app.core.Evaluations.recipe_runs_jobs import (
    RECIPE_RUN_JOB_DOMAIN,
    RECIPE_RUN_JOB_TYPE,
    build_recipe_run_idempotency_key,
    build_recipe_run_job_payload,
    enqueue_recipe_run,
    recipe_run_queue,
)
from tldw_Server_API.app.core.Evaluations.recipe_runs_jobs_worker import (
    handle_recipe_run_job,
    start_recipe_run_jobs_worker,
)
from tldw_Server_API.app.core.Evaluations.recipe_runs_service import RecipeRunsService


def _inline_dataset() -> list[dict[str, Any]]:
    return [
        {
            "input": "Summarize the notes.",
            "expected": "A short summary.",
        }
    ]


def _run_config() -> dict[str, Any]:
    return {
        "candidate_model_ids": ["openai:gpt-4.1-mini"],
        "judge_config": {"provider": "openai", "model": "gpt-4.1-mini"},
        "prompts": {"system": "Grade carefully."},
        "weights": {"quality": 1.0},
        "comparison_mode": "leaderboard",
        "source_normalization": {},
        "context_policy": {"mode": "recipe_default"},
        "execution_policy": {"max_parallel_candidates": 1},
    }


def _embeddings_dataset() -> list[dict[str, Any]]:
    return [
        {
            "query_id": "q-1",
            "input": "find alpha",
            "expected_ids": ["1"],
        },
        {
            "query_id": "q-2",
            "input": "find beta",
            "expected_ids": ["2"],
        },
    ]


def _embeddings_run_config() -> dict[str, Any]:
    return {
        "comparison_mode": "embedding_only",
        "candidates": [
            {"provider": "openai", "model": "text-embedding-3-small"},
            {"provider": "local", "model": "bge-small", "is_local": True},
        ],
        "media_ids": [1, 2],
    }


def _service(tmp_path) -> tuple[EvaluationsDatabase, RecipeRunsService, str]:
    db = EvaluationsDatabase(str(tmp_path / "evaluations.db"))
    user_id = get_single_user_instance().id_str
    return db, RecipeRunsService(db=db, user_id=user_id), user_id


def test_enqueue_recipe_run_uses_jobs_contract(tmp_path) -> None:
    _, service, user_id = _service(tmp_path)
    record = service.create_run(
        "summarization_quality",
        dataset=_inline_dataset(),
        run_config=_run_config(),
    )
    captured: dict[str, Any] = {}

    class _JobManager:
        def create_job(self, **kwargs):
            captured.update(kwargs)
            return {"id": 123}

    job_id = enqueue_recipe_run(record, owner_user_id=user_id, job_manager=_JobManager())

    assert job_id == "123"
    assert captured["domain"] == RECIPE_RUN_JOB_DOMAIN
    assert captured["queue"] == recipe_run_queue()
    assert captured["job_type"] == RECIPE_RUN_JOB_TYPE
    assert captured["owner_user_id"] == user_id
    assert captured["payload"] == build_recipe_run_job_payload(
        run_id=record.run_id,
        recipe_id=record.recipe_id,
        owner_user_id=user_id,
    )
    assert captured["idempotency_key"] == build_recipe_run_idempotency_key(run_id=record.run_id)


def test_handle_recipe_run_job_marks_run_completed_with_normalized_report(tmp_path) -> None:
    db, service, user_id = _service(tmp_path)
    record = service.create_run(
        "summarization_quality",
        dataset=_inline_dataset(),
        run_config=_run_config(),
    )

    result = handle_recipe_run_job(
        {
            "id": "job-42",
            "payload": build_recipe_run_job_payload(
                run_id=record.run_id,
                recipe_id=record.recipe_id,
                owner_user_id=user_id,
            ),
        },
        db=db,
        user_id=user_id,
    )

    refreshed = db.get_recipe_run(record.run_id)

    assert result["status"] == "completed"
    assert result["run_id"] == record.run_id
    assert result["job_id"] == "job-42"
    assert refreshed is not None
    assert refreshed.status is RunStatus.COMPLETED
    assert set(refreshed.recommendation_slots) == {
        "best_overall",
        "best_cheap",
        "best_local",
    }
    assert refreshed.metadata["jobs"]["job_id"] == "job-42"
    assert refreshed.metadata["jobs"]["worker_state"] == "completed"


def test_handle_recipe_run_job_marks_run_failed_when_report_building_errors(tmp_path) -> None:
    db, service, user_id = _service(tmp_path)
    record = service.create_run(
        "summarization_quality",
        dataset=_inline_dataset(),
        run_config=_run_config(),
    )

    class _BrokenService:
        def get_run(self, run_id: str):
            assert run_id == record.run_id
            return service.get_run(run_id)

        def get_report(self, run_id: str):
            assert run_id == record.run_id
            raise RuntimeError("boom")

    try:
        handle_recipe_run_job(
            {
                "id": "job-99",
                "payload": build_recipe_run_job_payload(
                    run_id=record.run_id,
                    recipe_id=record.recipe_id,
                    owner_user_id=user_id,
                ),
            },
            db=db,
            user_id=user_id,
            service=_BrokenService(),
        )
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected RuntimeError")

    refreshed = db.get_recipe_run(record.run_id)
    assert refreshed is not None
    assert refreshed.status is RunStatus.FAILED
    assert refreshed.metadata["jobs"]["worker_state"] == "failed"
    assert refreshed.metadata["jobs"]["error"] == "boom"


def test_handle_recipe_run_job_executes_embeddings_recipe_and_persists_child_artifacts(
    tmp_path,
    monkeypatch,
) -> None:
    db, service, user_id = _service(tmp_path)
    dataset = _embeddings_dataset()
    record = service.create_run(
        "embeddings_model_selection",
        dataset=dataset,
        run_config=_embeddings_run_config(),
    )

    import tldw_Server_API.app.core.Evaluations.recipe_runs_jobs_worker as worker

    captured: dict[str, Any] = {}

    def _fake_execute(*, record, db, user_id, service):
        del db, service
        captured["run_id"] = record.run_id
        captured["inline_dataset"] = record.metadata.get("inline_dataset")
        captured["user_id"] = user_id
        return {
            "child_run_ids": ["arm-1"],
            "metadata": {
                "abtest": {"test_id": "abtest-child-1"},
                "candidate_results": [
                    {
                        "candidate_id": "arm-1",
                        "candidate_run_id": "arm-1",
                        "model": "text-embedding-3-small",
                        "provider": "openai",
                        "query_results": [
                            {
                                "ranked_ids": ["1"],
                                "expected_ids": ["1"],
                                "latency_ms": 80.0,
                            },
                            {
                                "ranked_ids": ["2"],
                                "expected_ids": ["2"],
                                "latency_ms": 90.0,
                            },
                        ],
                    }
                ],
                "recipe_report_inputs": {
                    "dataset_mode": "labeled",
                    "review_sample": {
                        "required": False,
                        "sample_size": 0,
                        "sample_query_ids": [],
                    },
                    "candidate_results": [
                        {
                            "candidate_id": "arm-1",
                            "candidate_run_id": "arm-1",
                            "model": "text-embedding-3-small",
                            "provider": "openai",
                            "query_results": [
                                {
                                    "ranked_ids": ["1"],
                                    "expected_ids": ["1"],
                                    "latency_ms": 80.0,
                                },
                                {
                                    "ranked_ids": ["2"],
                                    "expected_ids": ["2"],
                                    "latency_ms": 90.0,
                                },
                            ],
                        }
                    ],
                },
            },
        }

    monkeypatch.setattr(
        worker,
        "_execute_embeddings_recipe_run",
        _fake_execute,
        raising=False,
    )

    result = worker.handle_recipe_run_job(
        {
            "id": "job-embeddings",
            "payload": build_recipe_run_job_payload(
                run_id=record.run_id,
                recipe_id=record.recipe_id,
                owner_user_id=user_id,
            ),
        },
        db=db,
        user_id=user_id,
    )

    refreshed = db.get_recipe_run(record.run_id)

    assert result["status"] == "completed"
    assert captured["run_id"] == record.run_id
    assert captured["inline_dataset"] == dataset
    assert captured["user_id"] == user_id
    assert refreshed is not None
    assert refreshed.status is RunStatus.COMPLETED
    assert refreshed.child_run_ids == ["arm-1"]
    assert refreshed.metadata["abtest"]["test_id"] == "abtest-child-1"
    assert refreshed.metadata["candidate_results"]
    assert refreshed.metadata["recipe_report_inputs"]["candidate_results"]
    assert refreshed.metadata["recipe_report"]["best_overall"]["candidate_id"] == "arm-1"
    assert refreshed.metadata["jobs"]["worker_state"] == "completed"
    assert refreshed.recommendation_slots["best_overall"].candidate_run_id == "arm-1"


@pytest.mark.asyncio
async def test_start_recipe_run_jobs_worker_respects_enable_flag(monkeypatch) -> None:
    monkeypatch.delenv("EVALUATIONS_RECIPE_RUN_JOBS_WORKER_ENABLED", raising=False)
    monkeypatch.delenv("EVALS_RECIPE_RUN_JOBS_WORKER_ENABLED", raising=False)

    task = await start_recipe_run_jobs_worker()

    assert task is None


@pytest.mark.asyncio
async def test_start_recipe_run_jobs_worker_returns_task_when_enabled(monkeypatch) -> None:
    started = asyncio.Event()
    finished = asyncio.Event()

    async def _fake_run():
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            finished.set()
            raise

    monkeypatch.setenv("EVALUATIONS_RECIPE_RUN_JOBS_WORKER_ENABLED", "true")
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Evaluations.recipe_runs_jobs_worker.run_recipe_run_jobs_worker",
        _fake_run,
    )

    task = await start_recipe_run_jobs_worker()
    assert task is not None
    await asyncio.wait_for(started.wait(), timeout=1.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()
