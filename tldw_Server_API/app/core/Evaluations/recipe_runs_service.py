from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass, field
from typing import Any, Mapping

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import (
    get_unified_evaluation_service_for_user,
)


RECIPE_RUN_REUSE_ENTITY_TYPE = "recipe_run"
RECIPE_RUN_ID_PREFIX = "recipe_run"
RECIPE_ID = "rag_retrieval_tuning"
RECIPE_VERSION = "v1"


class RecipeRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(..., min_length=1)
    candidate_models: list[str] = Field(default_factory=list)
    data_mode: str = Field(default="labeled")
    dataset_version: str | None = None
    run_config: dict[str, Any] = Field(default_factory=dict)
    force_rerun: bool = False


class RecipeDatasetValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str | None = None
    candidate_models: list[str] = Field(default_factory=list)
    data_mode: str = Field(default="labeled")
    dataset_version: str | None = None
    run_config: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class RecipeManifest:
    id: str
    version: str
    display_name: str
    description: str
    recommendation_slots: tuple[str, ...] = ("best_overall", "best_cheap", "best_local")

    def model_dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "display_name": self.display_name,
            "description": self.description,
            "recommendation_slots": list(self.recommendation_slots),
        }


def _recipe_manifest() -> RecipeManifest:
    return RecipeManifest(
        id=RECIPE_ID,
        version=RECIPE_VERSION,
        display_name="RAG Retrieval Tuning",
        description="Tune retrieval settings against labeled or unlabeled corpora.",
    )


def list_recipe_manifests() -> list[dict[str, Any]]:
    return [_recipe_manifest().model_dump()]


def get_recipe_manifest(recipe_id: str) -> dict[str, Any]:
    if recipe_id != RECIPE_ID:
        raise KeyError(recipe_id)
    return _recipe_manifest().model_dump()


def _coerce_request_payload(payload: Mapping[str, Any] | RecipeRunRequest | RecipeDatasetValidationRequest) -> dict[str, Any]:
    if isinstance(payload, BaseModel):
        return payload.model_dump()
    return dict(payload)


def _stable_json_dumps(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def compute_recipe_run_hash(
    payload: Mapping[str, Any] | RecipeRunRequest,
    *,
    recipe_id: str | None = None,
    recipe_version: str | None = None,
) -> str:
    data = _coerce_request_payload(payload)
    normalized = {
        "recipe_id": recipe_id or data.get("recipe_id") or RECIPE_ID,
        "recipe_version": recipe_version or data.get("recipe_version") or RECIPE_VERSION,
        "dataset_id": data.get("dataset_id"),
        "dataset_version": data.get("dataset_version"),
        "candidate_models": list(data.get("candidate_models") or []),
        "data_mode": data.get("data_mode") or "labeled",
        "run_config": data.get("run_config") or {},
    }
    digest = hashlib.sha256(_stable_json_dumps(normalized).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _normalize_candidate(candidate: Mapping[str, Any] | str, index: int) -> dict[str, Any]:
    if isinstance(candidate, str):
        return {
            "model": candidate,
            "score": max(0.0, 1.0 - (index * 0.1)),
            "cost_usd": float(index + 1) * 0.01,
            "latency_ms": float(index + 1) * 100.0,
            "is_local": False,
            "passed_gate": True,
        }
    normalized = dict(candidate)
    normalized.setdefault("model", f"candidate_{index}")
    normalized.setdefault("score", 0.0)
    normalized.setdefault("cost_usd", None)
    normalized.setdefault("latency_ms", None)
    normalized.setdefault("is_local", False)
    normalized.setdefault("passed_gate", True)
    return normalized


def _pick_best(candidates: list[dict[str, Any]], *, key: str) -> dict[str, Any] | None:
    if not candidates:
        return None
    if key == "cost_usd":
        with_cost = [candidate for candidate in candidates if candidate.get("cost_usd") is not None]
        if not with_cost:
            return None
        return min(with_cost, key=lambda candidate: float(candidate.get("cost_usd") or 0.0))
    return max(candidates, key=lambda candidate: float(candidate.get("score") or 0.0))


def _confidence_from_candidates(candidates: list[dict[str, Any]], *, winner: dict[str, Any] | None, data_mode: str) -> dict[str, Any]:
    scores = [float(candidate.get("score") or 0.0) for candidate in candidates]
    sample_count = len(scores)
    variance = float(statistics.pvariance(scores)) if len(scores) > 1 else 0.0
    ranked = sorted(scores, reverse=True)
    winner_margin = float(ranked[0] - ranked[1]) if len(ranked) > 1 else (float(ranked[0]) if ranked else 0.0)
    warning_codes: list[str] = []
    if sample_count < 3:
        warning_codes.append("low_sample")
    if len(ranked) > 1 and winner_margin < 0.05:
        warning_codes.append("close_call")
    if data_mode == "unlabeled":
        warning_codes.append("unlabeled_review_sample_reserved")
    judge_agreement = None
    if winner and isinstance(winner.get("judge_agreement"), (int, float)):
        judge_agreement = float(winner["judge_agreement"])
    return {
        "sample_count": sample_count,
        "variance": variance,
        "winner_margin": winner_margin,
        "judge_agreement": judge_agreement,
        "warning_codes": warning_codes,
    }


def build_rag_retrieval_tuning_report(
    candidate_results: list[Mapping[str, Any] | str],
    *,
    data_mode: str = "labeled",
    run_id: str | None = None,
    recipe_version: str = RECIPE_VERSION,
) -> dict[str, Any]:
    candidates = [_normalize_candidate(candidate, index) for index, candidate in enumerate(candidate_results)]
    passed_gate = [candidate for candidate in candidates if bool(candidate.get("passed_gate", True))]

    best_overall = _pick_best(passed_gate, key="score")
    best_cheap = _pick_best(passed_gate, key="cost_usd")
    local_candidates = [candidate for candidate in passed_gate if bool(candidate.get("is_local"))]
    best_local = _pick_best(local_candidates, key="score")

    report: dict[str, Any] = {
        "id": run_id,
        "object": "recipe_report",
        "recipe_id": RECIPE_ID,
        "recipe_version": recipe_version,
        "candidate_results": candidates,
        "best_overall": best_overall,
        "best_overall_reason_code": None,
        "best_overall_explanation": None,
        "best_cheap": best_cheap,
        "best_cheap_reason_code": None,
        "best_cheap_explanation": None,
        "best_local": best_local,
        "best_local_reason_code": None,
        "best_local_explanation": None,
        "review_state": "not_required",
    }

    if best_overall is None:
        report["best_overall_reason_code"] = "no_candidate_passed_grounding"
        report["best_overall_explanation"] = "No candidate satisfied the grounding gate."
    if best_cheap is None:
        report["best_cheap_reason_code"] = "no_candidate_with_cost"
        report["best_cheap_explanation"] = "No candidate included cost information."
    if best_local is None:
        report["best_local_reason_code"] = "no_local_candidate"
        report["best_local_explanation"] = "No local candidate satisfied the selection criteria."

    confidence = _confidence_from_candidates(candidates, winner=best_overall, data_mode=data_mode)
    report["confidence"] = confidence

    if data_mode == "unlabeled" or "low_sample" in confidence["warning_codes"] or "close_call" in confidence["warning_codes"]:
        report["review_state"] = "review_required"

    report["child_run_ids"] = [f"{run_id}:candidate:{index}" if run_id else f"candidate:{index}" for index in range(len(candidates))]
    return report


@dataclass
class RecipeRunsService:
    user_id: str
    db: Any | None = None
    _svc: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.user_id = str(self.user_id)
        self._svc = None
        if self.db is None:
            self._svc = get_unified_evaluation_service_for_user(self.user_id)
            self.db = self._svc.db
        if self.db is None:
            raise RuntimeError("Evaluations database is unavailable")

    def list_recipes(self) -> list[dict[str, Any]]:
        return list_recipe_manifests()

    def get_recipe_manifest(self, recipe_id: str) -> dict[str, Any]:
        return get_recipe_manifest(recipe_id)

    def validate_recipe_dataset(
        self,
        recipe_id: str,
        payload: Mapping[str, Any] | RecipeDatasetValidationRequest | RecipeRunRequest,
    ) -> dict[str, Any]:
        data = _coerce_request_payload(payload)
        errors: list[str] = []
        if recipe_id != RECIPE_ID:
            errors.append(f"unsupported recipe_id: {recipe_id}")
        if not str(data.get("dataset_id") or "").strip():
            errors.append("dataset_id is required")
        if not list(data.get("candidate_models") or []):
            errors.append("candidate_models is required")
        if data.get("data_mode") not in {"labeled", "unlabeled"}:
            errors.append("data_mode must be labeled or unlabeled")
        return {"valid": not errors, "errors": errors}

    def _normalize_request(self, payload: Mapping[str, Any] | RecipeRunRequest) -> dict[str, Any]:
        data = _coerce_request_payload(payload)
        data.setdefault("data_mode", "labeled")
        data.setdefault("run_config", {})
        data.setdefault("candidate_models", [])
        data.setdefault("dataset_version", None)
        data.setdefault("force_rerun", False)
        return data

    def create_recipe_run(
        self,
        recipe_id: str,
        payload: Mapping[str, Any] | RecipeRunRequest,
        *,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        if recipe_id != RECIPE_ID:
            raise KeyError(recipe_id)

        request = self._normalize_request(payload)
        validation = self.validate_recipe_dataset(recipe_id, request)
        if not validation["valid"]:
            raise ValueError("; ".join(validation["errors"]))

        config_hash = compute_recipe_run_hash(request, recipe_id=recipe_id, recipe_version=RECIPE_VERSION)
        idempotency_key = f"{RECIPE_RUN_ID_PREFIX}:{config_hash}"
        stable_user_id = str(created_by or self.user_id)

        if not bool(request.get("force_rerun")):
            existing_id = self.db.lookup_idempotency(RECIPE_RUN_REUSE_ENTITY_TYPE, idempotency_key, stable_user_id)
            if existing_id:
                existing = self.get_recipe_run(existing_id, created_by=stable_user_id)
                if existing:
                    existing = dict(existing)
                    existing["reused"] = True
                    existing["config_hash"] = config_hash
                    return existing

        run_config = dict(request.get("run_config") or {})
        review_state = "review_required" if request.get("data_mode") == "unlabeled" else "not_required"
        run_config.update(
            {
                "recipe_id": recipe_id,
                "recipe_version": RECIPE_VERSION,
                "dataset_id": request["dataset_id"],
                "dataset_version": request.get("dataset_version"),
                "candidate_models": list(request.get("candidate_models") or []),
                "data_mode": request.get("data_mode") or "labeled",
                "config_hash": config_hash,
                "review_state": review_state,
            }
        )
        run_id = self.db.create_run(
            eval_id=f"recipe:{recipe_id}",
            target_model=(request.get("candidate_models") or [None])[0],
            config=run_config,
        )
        self.db.record_idempotency(RECIPE_RUN_REUSE_ENTITY_TYPE, idempotency_key, run_id, stable_user_id)
        run = self.get_recipe_run(run_id, created_by=stable_user_id)
        if not run:
            raise RuntimeError(f"failed to load newly created recipe run {run_id}")
        run["reused"] = False
        return run

    def get_recipe_run(self, run_id: str, *, created_by: str | None = None) -> dict[str, Any] | None:
        row = self.db.get_run(run_id, created_by=created_by or self.user_id)
        if not row:
            return None
        config = dict(row.get("config") or {})
        result = {
            "id": row["id"],
            "object": "recipe_run",
            "recipe_id": config.get("recipe_id") or RECIPE_ID,
            "recipe_version": config.get("recipe_version") or RECIPE_VERSION,
            "dataset_id": config.get("dataset_id"),
            "dataset_version": config.get("dataset_version"),
            "candidate_models": list(config.get("candidate_models") or []),
            "data_mode": config.get("data_mode") or "labeled",
            "run_config": dict(config),
            "config_hash": config.get("config_hash"),
            "status": row.get("status"),
            "review_state": (row.get("results") or {}).get("review_state") if isinstance(row.get("results"), dict) else config.get("review_state"),
            "reused": False,
            "child_run_ids": (row.get("progress") or {}).get("child_run_ids") if isinstance(row.get("progress"), dict) else [],
        }
        if isinstance(row.get("results"), dict):
            result["report"] = row["results"]
        return result

    def get_recipe_report(self, run_id: str, *, created_by: str | None = None) -> dict[str, Any] | None:
        run = self.db.get_run(run_id, created_by=created_by or self.user_id)
        if not run:
            return None
        if isinstance(run.get("results"), dict):
            return run["results"]
        config = dict(run.get("config") or {})
        return build_rag_retrieval_tuning_report(
            list(config.get("candidate_results") or config.get("candidate_models") or []),
            data_mode=config.get("data_mode") or "labeled",
            run_id=run_id,
            recipe_version=config.get("recipe_version") or RECIPE_VERSION,
        )

    async def execute_recipe_run(
        self,
        *,
        run_id: str,
        recipe_id: str,
        run_config: Mapping[str, Any] | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        if recipe_id != RECIPE_ID:
            raise KeyError(recipe_id)

        run = self.db.get_run(run_id, created_by=created_by or self.user_id)
        if not run:
            raise KeyError(run_id)

        config = dict(run.get("config") or {})
        effective_config = dict(run_config or {})
        if not effective_config:
            effective_config = dict(config.get("run_config") or {})
        candidate_results = list(effective_config.get("candidate_results") or config.get("candidate_results") or [])
        if not candidate_results:
            candidate_results = list(effective_config.get("candidate_models") or config.get("candidate_models") or [])

        report = build_rag_retrieval_tuning_report(
            candidate_results,
            data_mode=effective_config.get("data_mode") or config.get("data_mode") or "labeled",
            run_id=run_id,
            recipe_version=config.get("recipe_version") or RECIPE_VERSION,
        )
        report["run_id"] = run_id
        report["recipe_id"] = recipe_id
        logger.debug(f"Built rag_retrieval_tuning report for run {run_id}")
        return report


def get_recipe_runs_service_for_user(user_id: str | int) -> RecipeRunsService:
    return RecipeRunsService(user_id=str(user_id))
