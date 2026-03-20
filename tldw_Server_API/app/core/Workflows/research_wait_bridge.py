"""Best-effort bridge for resuming workflows paused on research checkpoints."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.DB_Management.DB_Manager import create_workflows_database
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.Workflows.engine import WorkflowEngine


def _build_workflows_db() -> WorkflowsDatabase:
    """Return the default workflows database instance for resume handling."""
    return create_workflows_database()


def _build_workflow_engine(db: WorkflowsDatabase) -> WorkflowEngine:
    """Return a workflow engine bound to the provided database."""
    return WorkflowEngine(db)


def _coerce_wait_payload(raw_payload: Any) -> dict[str, Any]:
    if isinstance(raw_payload, dict):
        return raw_payload
    if isinstance(raw_payload, str):
        try:
            decoded = json.loads(raw_payload)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _is_wait_link_still_eligible(db: WorkflowsDatabase, link: dict[str, Any]) -> bool:
    run = db.get_run(str(link.get("workflow_run_id") or ""))
    if run is None or str(run.status) != "waiting_human":
        return False
    step_id = str(link.get("step_id") or "")
    if not step_id:
        return False
    step_run = db.get_latest_step_run(run_id=str(run.run_id), step_id=step_id)
    if not step_run:
        return False
    return str(step_run.get("status") or "") == "waiting_human"


def _schedule_resume(
    *,
    engine: WorkflowEngine,
    workflow_run_id: str,
    step_id: str,
    wait_payload: dict[str, Any],
) -> asyncio.Task[Any]:
    return asyncio.create_task(
        engine.continue_run(
            workflow_run_id,
            after_step_id=step_id,
            last_outputs=wait_payload,
            next_step_id=step_id,
        )
    )


async def resume_workflows_waiting_on_research_checkpoint(
    *,
    research_run_id: str,
    checkpoint_id: str,
) -> int:
    """Resume workflows linked to a resolved research checkpoint."""
    if not str(research_run_id).strip() or not str(checkpoint_id).strip():
        return 0

    try:
        db = _build_workflows_db()
        claimed = db.claim_research_waits_for_resume(
            research_run_id=research_run_id,
            checkpoint_id=checkpoint_id,
        )
        if not claimed:
            return 0

        engine = _build_workflow_engine(db)
        resumed = 0
        for item in claimed:
            wait_id = str(item.get("wait_id") or "")
            workflow_run_id = str(item.get("workflow_run_id") or "")
            step_id = str(item.get("step_id") or "")
            wait_payload = _coerce_wait_payload(item.get("wait_payload_json"))
            should_mark_resumed = False

            try:
                if not workflow_run_id or not step_id:
                    logger.warning(
                        "Skipping research-wait resume with missing linkage identifiers "
                        "research_run_id={} checkpoint_id={} wait_id={}",
                        research_run_id,
                        checkpoint_id,
                        wait_id,
                    )
                    continue
                if not _is_wait_link_still_eligible(db, item):
                    logger.debug(
                        "Skipping stale research-wait resume "
                        "research_run_id={} checkpoint_id={} workflow_run_id={} step_id={}",
                        research_run_id,
                        checkpoint_id,
                        workflow_run_id,
                        step_id,
                    )
                    continue
                _schedule_resume(
                    engine=engine,
                    workflow_run_id=workflow_run_id,
                    step_id=step_id,
                    wait_payload=wait_payload,
                )
                resumed += 1
                should_mark_resumed = True
            except Exception:
                logger.exception(
                    "Failed to schedule workflow resume for research checkpoint "
                    "research_run_id={} checkpoint_id={} workflow_run_id={} step_id={}",
                    research_run_id,
                    checkpoint_id,
                    workflow_run_id,
                    step_id,
                )
            finally:
                if wait_id:
                    try:
                        if should_mark_resumed:
                            db.mark_research_wait_resumed(wait_id=wait_id)
                        else:
                            db.reset_research_wait_for_retry(wait_id=wait_id)
                    except Exception:
                        logger.exception(
                            "Failed to update research wait status "
                            "research_run_id={} checkpoint_id={} wait_id={}",
                            research_run_id,
                            checkpoint_id,
                            wait_id,
                        )
        return resumed
    except Exception:
        logger.exception(
            "Failed to resume workflows waiting on research checkpoint "
            "research_run_id={} checkpoint_id={}",
            research_run_id,
            checkpoint_id,
        )
        return 0
