import copy

import pytest

from tldw_Server_API.app.core.Evaluations.recipe_runs_service import (
    RecipeRunsService,
    build_rag_retrieval_tuning_report,
    compute_recipe_run_hash,
)


class _StubDB:
    def __init__(self, *, existing_run: dict | None = None):
        self.existing_run = existing_run
        self.created_runs: list[dict] = []
        self.recorded_idempotency: list[tuple[str, str, str, str | None]] = []
        self.updated_status: list[tuple[str, str, str | None]] = []
        self.updated_progress: list[tuple[str, dict]] = []
        self.stored_results: list[tuple[str, dict, dict | None]] = []

    def lookup_idempotency(self, entity_type: str, key: str, user_id: str | None):
        if self.existing_run and entity_type == "recipe_run":
            return self.existing_run["id"]
        return None

    def record_idempotency(self, entity_type: str, key: str, entity_id: str, user_id: str | None):
        self.recorded_idempotency.append((entity_type, key, entity_id, user_id))

    def create_run(self, eval_id, target_model=None, config=None, webhook_url=None, *, run_id=None):
        run = {
            "id": run_id or "run_new",
            "object": "run",
            "created": 1,
            "created_at": 1,
            "eval_id": eval_id,
            "status": "pending",
            "target_model": target_model,
            "config": config or {},
            "progress": None,
            "results": None,
            "error_message": None,
            "started_at": None,
            "completed_at": None,
            "usage": None,
        }
        self.created_runs.append(run)
        return run["id"]

    def get_run(self, run_id: str, *, created_by: str | None = None):
        if self.existing_run and self.existing_run["id"] == run_id:
            return self.existing_run
        for run in self.created_runs:
            if run["id"] == run_id:
                return run
        return None

    def update_run_status(self, run_id: str, status: str, error_message: str | None = None) -> bool:
        self.updated_status.append((run_id, status, error_message))
        return True

    def update_run_progress(self, run_id: str, progress: dict) -> bool:
        self.updated_progress.append((run_id, progress))
        return True

    def store_run_results(self, run_id: str, results: dict, usage: dict | None = None) -> bool:
        self.stored_results.append((run_id, results, usage))
        for run in self.created_runs:
            if run["id"] == run_id:
                run["results"] = results
                run["usage"] = usage
                run["status"] = "completed"
        return True


@pytest.mark.unit
def test_rag_retrieval_tuning_hash_is_deterministic_and_sensitive():
    base = {
        "recipe_id": "rag_retrieval_tuning",
        "recipe_version": "v1",
        "dataset_id": "dataset_1",
        "dataset_version": "v1",
        "candidate_models": ["m1", "m2"],
        "data_mode": "labeled",
        "run_config": {"retrieval_mode": "embedding_only", "weights": {"recall": 0.7}},
    }
    mutated = copy.deepcopy(base)
    mutated["run_config"]["weights"]["recall"] = 0.8

    assert compute_recipe_run_hash(base) == compute_recipe_run_hash(base)
    assert compute_recipe_run_hash(base) != compute_recipe_run_hash(mutated)


@pytest.mark.unit
def test_rag_retrieval_tuning_reuses_completed_run_by_hash():
    existing_run = {
        "id": "run_123",
        "object": "run",
        "created": 1,
        "created_at": 1,
        "eval_id": "recipe:rag_retrieval_tuning",
        "status": "completed",
        "target_model": "m1",
        "config": {
            "recipe_id": "rag_retrieval_tuning",
            "recipe_version": "v1",
            "dataset_id": "dataset_1",
            "dataset_version": "v1",
            "candidate_models": ["m1", "m2"],
            "data_mode": "labeled",
            "run_config": {"retrieval_mode": "embedding_only"},
            "config_hash": "sha256:deadbeef",
        },
        "progress": {"child_run_ids": ["child_1"]},
        "results": {
            "best_overall": {"model": "m1"},
            "best_cheap": {"model": "m1"},
            "best_local": None,
        },
        "error_message": None,
        "started_at": 1,
        "completed_at": 2,
        "usage": None,
    }
    db = _StubDB(existing_run=existing_run)
    service = RecipeRunsService(user_id="user-1", db=db)

    request = {
        "dataset_id": "dataset_1",
        "dataset_version": "v1",
        "candidate_models": ["m1", "m2"],
        "data_mode": "labeled",
        "run_config": {"retrieval_mode": "embedding_only"},
        "force_rerun": False,
    }

    run = service.create_recipe_run("rag_retrieval_tuning", request)

    assert run["id"] == "run_123"
    assert run["status"] == "completed"
    assert run["reused"] is True
    assert db.created_runs == []


@pytest.mark.unit
def test_rag_retrieval_tuning_report_uses_null_fallbacks_and_confidence():
    report = build_rag_retrieval_tuning_report(
        [
            {
                "model": "remote-m1",
                "score": 0.91,
                "cost_usd": 0.20,
                "latency_ms": 120.0,
                "is_local": False,
                "passed_gate": False,
            },
            {
                "model": "remote-m2",
                "score": 0.88,
                "cost_usd": 0.18,
                "latency_ms": 150.0,
                "is_local": False,
                "passed_gate": False,
            },
        ],
        data_mode="unlabeled",
    )

    assert report["best_overall"] is None
    assert report["best_overall_reason_code"] == "no_candidate_passed_grounding"
    assert report["best_cheap"] is None
    assert report["best_local"] is None
    assert report["review_state"] == "review_required"
    assert report["confidence"]["sample_count"] == 2
    assert "warning_codes" in report["confidence"]
