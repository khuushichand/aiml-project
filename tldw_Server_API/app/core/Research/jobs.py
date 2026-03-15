"""Core Jobs helpers for deep research execution slices."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore
from tldw_Server_API.app.core.Research.planner import build_initial_plan

RESEARCH_DOMAIN = "research"
RESEARCH_JOB_TYPE = "research_phase"
RESEARCH_QUEUE = "default"


def enqueue_research_phase_job(
    *,
    jm: Any,
    session_id: str,
    phase: str,
    owner_user_id: str,
    checkpoint_id: str | None = None,
    policy_version: int = 1,
    priority: int = 5,
) -> dict[str, Any]:
    """Create a core Jobs entry for a research session phase."""
    return jm.create_job(
        domain=RESEARCH_DOMAIN,
        queue=RESEARCH_QUEUE,
        job_type=RESEARCH_JOB_TYPE,
        payload={
            "session_id": session_id,
            "phase": phase,
            "checkpoint_id": checkpoint_id,
            "policy_version": int(policy_version),
        },
        owner_user_id=str(owner_user_id),
        priority=priority,
        idempotency_key=f"research:{session_id}:{phase}:{checkpoint_id or 'none'}:{policy_version}",
    )


async def handle_research_phase_job(
    job: dict[str, Any],
    *,
    research_db_path: str | Path,
    outputs_dir: str | Path,
) -> dict[str, Any]:
    """Advance a single research phase job."""
    payload = job.get("payload") or {}
    job_type = str(job.get("job_type") or payload.get("job_type") or RESEARCH_JOB_TYPE).strip().lower()
    if job_type != RESEARCH_JOB_TYPE:
        raise ValueError(f"unsupported research job type: {job_type}")

    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("missing research session_id")

    phase = str(payload.get("phase") or "").strip().lower()
    if phase != "drafting_plan":
        raise ValueError(f"unsupported research phase: {phase}")

    db = ResearchSessionsDB(research_db_path)
    session = db.get_session(session_id)
    if session is None:
        raise KeyError(session_id)

    plan = build_initial_plan(
        query=session.query,
        source_policy=session.source_policy,
        autonomy_mode=session.autonomy_mode,
    )

    artifact_store = ResearchArtifactStore(base_dir=outputs_dir, db=db)
    artifact_store.write_json(
        owner_user_id=session.owner_user_id,
        session_id=session.id,
        artifact_name="plan.json",
        payload=asdict(plan),
        phase=session.phase,
        job_id=str(job.get("id")) if job.get("id") is not None else None,
    )

    next_phase = "collecting"
    next_status = "queued"
    checkpoint_id: str | None = None
    if session.autonomy_mode == "checkpointed":
        checkpoint = db.create_checkpoint(
            session_id=session.id,
            checkpoint_type="plan_review",
            proposed_payload=asdict(plan),
        )
        checkpoint_id = checkpoint.id
        next_phase = "awaiting_plan_review"
        next_status = "waiting_human"

    db.update_phase(session.id, phase=next_phase, status=next_status)
    db.attach_active_job(session.id, None)
    return {
        "session_id": session.id,
        "phase": next_phase,
        "checkpoint_id": checkpoint_id,
        "artifacts_written": 1,
    }


__all__ = [
    "RESEARCH_DOMAIN",
    "RESEARCH_JOB_TYPE",
    "RESEARCH_QUEUE",
    "enqueue_research_phase_job",
    "handle_research_phase_job",
]
