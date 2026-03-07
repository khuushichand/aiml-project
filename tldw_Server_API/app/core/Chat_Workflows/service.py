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
        run = self._require_run(run_id)
        template_snapshot = self._get_template_snapshot(run)
        current_step_index = int(run["current_step_index"])
        steps = template_snapshot["steps"]
        if current_step_index >= len(steps):
            return None

        step = steps[current_step_index]
        cached_question = self._get_rendered_question_cache(run_id, current_step_index)
        if cached_question is None:
            cached_question = await self._render_question_async(
                step=step,
                prior_answers=self.db.list_answers(run_id),
                context_snapshot=_json_loads(
                    run.get("resolved_context_snapshot_json"),
                    default=[],
                ),
                model=run.get("question_renderer_model"),
            )
            self.db.append_event(
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
    ) -> dict[str, Any]:
        run = self._require_run(run_id)
        current_step_index = int(run["current_step_index"])
        if step_index != current_step_index:
            raise ValueError(
                f"invalid step submission: expected step submission for index {current_step_index}"
            )

        template_snapshot = self._get_template_snapshot(run)
        steps = template_snapshot["steps"]
        if current_step_index >= len(steps):
            raise ValueError("run is already complete")

        step = steps[current_step_index]
        rendered_question = self._get_rendered_question_cache(run_id, current_step_index)
        if rendered_question is None:
            rendered_question = await self._render_question_async(
                step=step,
                prior_answers=self.db.list_answers(run_id),
                context_snapshot=_json_loads(
                    run.get("resolved_context_snapshot_json"),
                    default=[],
                ),
                model=run.get("question_renderer_model"),
            )
            self.db.append_event(
                run_id,
                "question_rendered",
                {
                    "step_index": current_step_index,
                    "step_id": step["id"],
                    **rendered_question,
                },
            )

        self.db.add_answer(
            run_id=run_id,
            step_id=step["id"],
            step_index=current_step_index,
            displayed_question=rendered_question["displayed_question"],
            answer_text=answer_text,
            question_generation_meta=rendered_question.get("question_generation_meta", {}),
        )

        next_step_index = current_step_index + 1
        if next_step_index >= len(steps):
            self.db.update_run(
                run_id,
                status="completed",
                current_step_index=next_step_index,
                completed_at=_utcnow_iso(),
            )
            self.db.append_event(
                run_id,
                "run_completed",
                {
                    "final_step_index": current_step_index,
                    "answer_count": len(self.db.list_answers(run_id)),
                },
            )
        else:
            self.db.update_run(
                run_id,
                status="active",
                current_step_index=next_step_index,
            )
            self.db.append_event(
                run_id,
                "step_answered",
                {
                    "answered_step_index": current_step_index,
                    "next_step_index": next_step_index,
                },
            )

        updated_run = self._require_run(run_id)
        result = dict(updated_run)
        result["answers"] = self.db.list_answers(run_id)
        if result["status"] == "active":
            result["current_step"] = await self.get_current_step(run_id)
        return result

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

    def _get_template_snapshot(self, run: dict[str, Any]) -> dict[str, Any]:
        snapshot = _json_loads(run.get("template_snapshot_json"), default={})
        steps = snapshot.get("steps", [])
        if not isinstance(steps, list):
            raise ValueError("run template snapshot is invalid")
        return snapshot

    def _get_rendered_question_cache(
        self,
        run_id: str,
        step_index: int,
    ) -> dict[str, Any] | None:
        events = self.db.list_events(run_id)
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
            logger.warning("Falling back to base question for chat workflow step: {}", exc)
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
