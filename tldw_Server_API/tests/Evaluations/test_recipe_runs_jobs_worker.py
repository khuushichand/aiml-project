import pytest

import tldw_Server_API.app.core.Evaluations.recipe_runs_jobs_worker as worker


class _StubDB:
    def __init__(self):
        self.status_updates: list[tuple[str, str, str | None]] = []
        self.progress_updates: list[tuple[str, dict]] = []
        self.results: list[tuple[str, dict, dict | None]] = []

    def update_run_status(self, run_id: str, status: str, error_message: str | None = None) -> bool:
        self.status_updates.append((run_id, status, error_message))
        return True

    def update_run_progress(self, run_id: str, progress: dict) -> bool:
        self.progress_updates.append((run_id, progress))
        return True

    def store_run_results(self, run_id: str, results: dict, usage: dict | None = None) -> bool:
        self.results.append((run_id, results, usage))
        return True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rag_retrieval_tuning_worker_executes_and_persists_report(monkeypatch):
    db = _StubDB()
    calls = {}

    class _StubService:
        def __init__(self):
            self.db = db

        async def execute_recipe_run(self, *, run_id: str, recipe_id: str, created_by: str | None, run_config: dict):
            calls["run_id"] = run_id
            calls["recipe_id"] = recipe_id
            calls["created_by"] = created_by
            calls["run_config"] = run_config
            report = {
                "run_id": run_id,
                "recipe_id": recipe_id,
                "best_overall": {"model": "m1"},
                "best_cheap": {"model": "m2"},
                "best_local": None,
                "best_local_reason_code": "no_local_candidate",
                "review_state": "not_required",
                "confidence": {"sample_count": 2, "variance": 0.0, "winner_margin": 0.12, "judge_agreement": None, "warning_codes": []},
            }
            return report

    monkeypatch.setattr(worker, "get_recipe_runs_service_for_user", lambda user_id: _StubService())

    job = {
        "job_type": worker.RECIPE_RUN_JOB_TYPE,
        "owner_user_id": "user-1",
        "payload": {
            "run_id": "recipe_run_1",
            "recipe_id": "rag_retrieval_tuning",
            "run_config": {"retrieval_mode": "embedding_only"},
        },
    }

    result = await worker.handle_recipe_run_job(job)

    assert result["run_id"] == "recipe_run_1"
    assert calls["recipe_id"] == "rag_retrieval_tuning"
    assert calls["created_by"] == "user-1"
    assert db.status_updates[0] == ("recipe_run_1", "running", None)
    assert db.results[0][0] == "recipe_run_1"
    assert db.progress_updates[0][1]["review_state"] == "not_required"
