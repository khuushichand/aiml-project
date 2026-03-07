from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Chat_Workflows.question_renderer import (
    ChatWorkflowQuestionRenderer,
)
from tldw_Server_API.app.core.DB_Management.ChatWorkflows_DB import (
    ChatWorkflowsDatabase,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_loads(value: str | None, *, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


class ChatWorkflowConflictError(ValueError):
    """Raised when a duplicate answer conflicts with the stored workflow state."""


class ChatWorkflowService:
    """Orchestrates chat workflow runs on top of the persistence adapter."""

    def __init__(
        self,
        *,
        db: ChatWorkflowsDatabase,
        question_renderer: ChatWorkflowQuestionRenderer | None,
    ) -> None:
        self.db = db
        self.question_renderer = question_renderer

    async def _db_call_async(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous DB adapter method on a worker thread."""
        method = getattr(self.db, method_name)
        return await asyncio.to_thread(method, *args, **kwargs)

    def start_run(
        self,
        *,
        tenant_id: str,
        user_id: str,
        template: dict[str, Any],
        source_mode: str,
        selected_context_refs: list[dict[str, Any]] | list[Any],
        question_renderer_model: str | None = None,
    ) -> dict[str, Any]:
        template_snapshot = self._normalize_template(template)
        if not template_snapshot["steps"]:
            raise ValueError("template must contain at least one step")
        template_id = template.get("id")
        if template_id is not None and self.db.get_template(int(template_id)) is None:
            template_id = None

        run_id = self.db.create_run(
            tenant_id=tenant_id,
            user_id=user_id,
            template_id=template_id,
            template_version=int(template_snapshot.get("version", 1)),
            source_mode=source_mode,
            status="active",
            template_snapshot=template_snapshot,
            selected_context_refs=selected_context_refs,
            resolved_context_snapshot=[],
            question_renderer_model=question_renderer_model,
        )
        self.db.append_event(
            run_id,
            "run_started",
            {
                "source_mode": source_mode,
                "step_count": len(template_snapshot["steps"]),
            },
        )
        return self._require_run(run_id)

    def generate_draft(
        self,
        *,
        goal: str,
        base_question: str | None = None,
        desired_step_count: int = 4,
    ) -> dict[str, Any]:
        normalized_goal = goal.strip()
        if not normalized_goal:
            raise ValueError("goal must not be empty")

        seed_questions = [
            base_question or f"What outcome do you want from {normalized_goal}?",
            f"What constraints should shape {normalized_goal}?",
            f"What context or assets already exist for {normalized_goal}?",
            f"What risks or unknowns could block {normalized_goal}?",
        ]
        while len(seed_questions) < desired_step_count:
            seed_questions.append(f"What else should be clarified about {normalized_goal}?")

        steps: list[dict[str, Any]] = []
        for step_index in range(desired_step_count):
            steps.append(
                {
                    "id": f"step-{step_index + 1}",
                    "step_index": step_index,
                    "label": f"Step {step_index + 1}",
                    "base_question": seed_questions[step_index],
                    "question_mode": "stock",
                    "context_refs": [],
                }
            )

        return {
            "title": normalized_goal,
            "description": f"Generated workflow for {normalized_goal}",
            "version": 1,
            "steps": steps,
        }

    async def get_current_step(self, run_id: str) -> dict[str, Any] | None:
        run = await self._require_run_async(run_id)
        template_snapshot = self._get_template_snapshot(run)
        current_step_index = int(run["current_step_index"])
        steps = template_snapshot["steps"]
        if current_step_index >= len(steps):
            return None

        step = steps[current_step_index]
        cached_question = await self._get_rendered_question_cache_async(
            run_id,
            current_step_index,
        )
        if cached_question is None:
            cached_question = await self._render_question_async(
                run_id=run_id,
                step_index=current_step_index,
                step=step,
                prior_answers=await self._db_call_async("list_answers", run_id),
                context_snapshot=_json_loads(
                    run.get("resolved_context_snapshot_json"),
                    default=[],
                ),
                model=run.get("question_renderer_model"),
            )
            await self._db_call_async(
                "append_event",
                run_id,
                "question_rendered",
                {
                    "step_index": current_step_index,
                    "step_id": step["id"],
                    **cached_question,
                },
            )

        return {
            **step,
            **cached_question,
            "run_id": run_id,
            "step_index": current_step_index,
        }

    async def record_answer(
        self,
        *,
        run_id: str,
        step_index: int,
        answer_text: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if idempotency_key is not None:
            existing_by_key = await self._db_call_async(
                "get_answer_by_idempotency_key",
                run_id,
                idempotency_key,
            )
            if existing_by_key is not None:
                self._validate_replayed_answer(
                    existing_answer=existing_by_key,
                    step_index=step_index,
                    answer_text=answer_text,
                )
                return await self._build_run_result(run_id)

        run = await self._require_run_async(run_id)
        current_step_index = int(run["current_step_index"])
        if step_index != current_step_index:
            existing_answer = await self._db_call_async("get_answer", run_id, step_index)
            if existing_answer is not None and existing_answer["answer_text"] == answer_text:
                return await self._build_run_result(run_id)
            raise ValueError(
                f"invalid step submission: expected step submission for index {current_step_index}"
            )
        if run.get("status") != "active":
            existing_answer = await self._db_call_async("get_answer", run_id, step_index)
            if existing_answer is not None and existing_answer["answer_text"] == answer_text:
                return await self._build_run_result(run_id)
            raise ValueError("run is not active")

        template_snapshot = self._get_template_snapshot(run)
        steps = template_snapshot["steps"]
        if current_step_index >= len(steps):
            raise ValueError("run is already complete")

        step = steps[current_step_index]
        rendered_question = await self._get_rendered_question_cache_async(
            run_id,
            current_step_index,
        )
        if rendered_question is None:
            rendered_question = await self._render_question_async(
                run_id=run_id,
                step_index=current_step_index,
                step=step,
                prior_answers=await self._db_call_async("list_answers", run_id),
                context_snapshot=_json_loads(
                    run.get("resolved_context_snapshot_json"),
                    default=[],
                ),
                model=run.get("question_renderer_model"),
            )
            await self._db_call_async(
                "append_event",
                run_id,
                "question_rendered",
                {
                    "step_index": current_step_index,
                    "step_id": step["id"],
                    **rendered_question,
                },
            )

        next_step_index = current_step_index + 1
        is_final_step = next_step_index >= len(steps)
        transition = await self._db_call_async(
            "record_answer_transition",
            run_id=run_id,
            expected_step_index=current_step_index,
            next_step_index=next_step_index,
            next_status="completed" if is_final_step else "active",
            completed_at=_utcnow_iso() if is_final_step else None,
            step_id=step["id"],
            displayed_question=rendered_question["displayed_question"],
            answer_text=answer_text,
            question_generation_meta=rendered_question.get("question_generation_meta", {}),
            idempotency_key=idempotency_key,
        )

        if transition["outcome"] == "replayed":
            return await self._build_run_result(run_id)
        if transition["outcome"] == "stale":
            raise ValueError(
                f"invalid step submission: expected step submission for index "
                f"{int(transition['run']['current_step_index'])}"
            )
        if transition["outcome"] == "conflict":
            raise ChatWorkflowConflictError(
                "idempotency key has already been used for a different answer"
                if transition.get("reason") == "idempotency_key_reused"
                else "step already contains a different answer"
            )

        if is_final_step:
            await self._db_call_async(
                "append_event",
                run_id,
                "run_completed",
                {
                    "final_step_index": current_step_index,
                    "answer_count": len(await self._db_call_async("list_answers", run_id)),
                },
            )
        else:
            await self._db_call_async(
                "append_event",
                run_id,
                "step_answered",
                {
                    "answered_step_index": current_step_index,
                    "next_step_index": next_step_index,
                },
            )

        return await self._build_run_result(run_id)

    def _normalize_template(self, template: dict[str, Any]) -> dict[str, Any]:
        normalized_steps: list[dict[str, Any]] = []
        for index, step in enumerate(template.get("steps", [])):
            normalized_steps.append(
                {
                    "id": str(step.get("id") or step.get("step_id") or f"step-{index + 1}"),
                    "step_index": int(step.get("step_index", index)),
                    "label": step.get("label"),
                    "base_question": str(step["base_question"]).strip(),
                    "question_mode": str(step.get("question_mode", "stock")).strip().lower().replace("-", "_"),
                    "phrasing_instructions": step.get("phrasing_instructions"),
                    "context_refs": list(step.get("context_refs", [])),
                }
            )
        return {
            "id": template.get("id"),
            "title": template.get("title") or "Untitled workflow",
            "description": template.get("description"),
            "version": int(template.get("version", 1)),
            "steps": normalized_steps,
        }

    def _require_run(self, run_id: str) -> dict[str, Any]:
        run = self.db.get_run(run_id)
        if run is None:
            raise ValueError(f"run not found: {run_id}")
        return run

    async def _require_run_async(self, run_id: str) -> dict[str, Any]:
        run = await self._db_call_async("get_run", run_id)
        if run is None:
            raise ValueError(f"run not found: {run_id}")
        return run

    async def _build_run_result(self, run_id: str) -> dict[str, Any]:
        run = await self._require_run_async(run_id)
        result = dict(run)
        result["answers"] = await self._db_call_async("list_answers", run_id)
        if result["status"] == "active":
            result["current_step"] = await self.get_current_step(run_id)
        return result

    def _validate_replayed_answer(
        self,
        *,
        existing_answer: dict[str, Any],
        step_index: int,
        answer_text: str,
    ) -> None:
        if int(existing_answer["step_index"]) != step_index:
            raise ChatWorkflowConflictError(
                "idempotency key has already been used for a different step"
            )
        if existing_answer["answer_text"] != answer_text:
            raise ChatWorkflowConflictError(
                "idempotency key has already been used for a different answer"
            )

    def _get_template_snapshot(self, run: dict[str, Any]) -> dict[str, Any]:
        snapshot = _json_loads(run.get("template_snapshot_json"), default={})
        steps = snapshot.get("steps", [])
        if not isinstance(steps, list):
            raise ValueError("run template snapshot is invalid")
        return snapshot

    async def _get_rendered_question_cache_async(
        self,
        run_id: str,
        step_index: int,
    ) -> dict[str, Any] | None:
        events = await self._db_call_async("list_events", run_id)
        for event in reversed(events):
            if event["event_type"] != "question_rendered":
                continue
            payload = _json_loads(event["payload_json"], default={})
            if int(payload.get("step_index", -1)) != step_index:
                continue
            return {
                "displayed_question": payload["displayed_question"],
                "question_generation_meta": payload.get("question_generation_meta", {}),
                "fallback_used": bool(payload.get("fallback_used", False)),
            }
        return None

    async def _render_question_async(
        self,
        *,
        run_id: str,
        step_index: int,
        step: dict[str, Any],
        prior_answers: list[dict[str, Any]],
        context_snapshot: list[dict[str, Any]] | list[Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        base_question = str(step.get("base_question") or "").strip()
        stock_result = {
            "displayed_question": base_question,
            "question_generation_meta": {"mode": "stock"},
            "fallback_used": False,
        }
        if step.get("question_mode") != "llm_phrased":
            return stock_result
        if self.question_renderer is None:
            return stock_result

        try:
            rendered = await self.question_renderer.render_question(
                base_question=base_question,
                phrasing_instructions=step.get("phrasing_instructions"),
                prior_answers=prior_answers,
                context_snapshot=context_snapshot,
                model=model,
            )
            displayed_question = str(rendered.get("displayed_question") or "").strip()
            if not displayed_question:
                raise ValueError("renderer returned an empty displayed_question")
            return {
                "displayed_question": displayed_question,
                "question_generation_meta": rendered.get("question_generation_meta", {}),
                "fallback_used": bool(rendered.get("fallback_used", False)),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Falling back to base question for chat workflow step "
                "run_id={} step_index={} step_id={} model={} error={}",
                run_id,
                step_index,
                step.get("id"),
                model,
                exc,
            )
            return {
                "displayed_question": base_question,
                "question_generation_meta": {
                    "mode": "fallback",
                    "error": str(exc),
                },
                "fallback_used": True,
            }

    def _render_question_sync(
        self,
        *,
        step: dict[str, Any],
        prior_answers: list[dict[str, Any]],
        context_snapshot: list[dict[str, Any]] | list[Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self._render_question_async(
                    run_id="sync-preview",
                    step_index=int(step.get("step_index", 0)),
                    step=step,
                    prior_answers=prior_answers,
                    context_snapshot=context_snapshot,
                    model=model,
                )
            )

        base_question = str(step.get("base_question") or "").strip()
        return {
            "displayed_question": base_question,
            "question_generation_meta": {"mode": "sync_fallback"},
            "fallback_used": True,
        }
