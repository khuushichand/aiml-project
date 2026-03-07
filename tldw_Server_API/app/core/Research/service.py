"""Service entrypoint for deep research sessions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import (
    ResearchSessionRow,
    ResearchSessionsDB,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Jobs.worker_utils import jobs_manager_from_env

from .artifact_store import ResearchArtifactStore
from .checkpoint_service import apply_checkpoint_patch
from .exporter import build_final_package
from .jobs import enqueue_research_phase_job


class ResearchService:
    """Create research sessions and enqueue the next executable slice."""

    def __init__(
        self,
        *,
        research_db_path: str | Path | None,
        outputs_dir: str | Path | None,
        job_manager: Any | None,
    ):
        self._research_db_path = Path(research_db_path) if research_db_path is not None else None
        self._outputs_dir = Path(outputs_dir) if outputs_dir is not None else None
        self._job_manager = job_manager

    def _db_for_user(self, owner_user_id: str) -> ResearchSessionsDB:
        if self._research_db_path is not None:
            return ResearchSessionsDB(self._research_db_path)
        return ResearchSessionsDB(DatabasePaths.get_research_sessions_db_path(owner_user_id))

    def _outputs_dir_for_user(self, owner_user_id: str) -> Path:
        if self._outputs_dir is not None:
            return self._outputs_dir
        return DatabasePaths.get_user_outputs_dir(owner_user_id)

    def _job_manager_for_session(self) -> Any:
        if self._job_manager is not None:
            return self._job_manager
        return jobs_manager_from_env()

    def create_session(
        self,
        *,
        owner_user_id: str,
        query: str,
        source_policy: str,
        autonomy_mode: str,
        limits_json: dict[str, Any] | None = None,
    ) -> ResearchSessionRow:
        """Create a research session and enqueue the planning phase."""
        db = self._db_for_user(owner_user_id)
        session = db.create_session(
            owner_user_id=owner_user_id,
            query=query,
            source_policy=source_policy,
            autonomy_mode=autonomy_mode,
            limits_json=limits_json or {},
        )

        job = enqueue_research_phase_job(
            jm=self._job_manager_for_session(),
            session_id=session.id,
            phase=session.phase,
            owner_user_id=session.owner_user_id,
        )
        job_id = job.get("id")
        active_job_id: str | None
        if job_id is not None:
            active_job_id = str(job_id)
        else:
            job_uuid = job.get("uuid")
            active_job_id = str(job_uuid) if job_uuid else None
        return db.attach_active_job(
            session.id,
            active_job_id,
        )

    def approve_checkpoint(
        self,
        *,
        owner_user_id: str,
        session_id: str,
        checkpoint_id: str,
        patch_payload: dict[str, Any] | None = None,
    ) -> ResearchSessionRow:
        """Resolve a review checkpoint and advance the session to the next phase."""
        db = self._db_for_user(owner_user_id)
        session = db.get_session(session_id)
        if session is None:
            raise KeyError(session_id)

        checkpoint = db.get_checkpoint(checkpoint_id)
        if checkpoint is None or checkpoint.session_id != session_id:
            raise KeyError(checkpoint_id)

        merged_payload = apply_checkpoint_patch(
            proposed_payload=checkpoint.proposed_payload,
            patch_payload=patch_payload or {},
        )
        db.resolve_checkpoint(
            checkpoint_id,
            resolution="patched" if patch_payload else "approved",
            user_patch_payload=patch_payload or {},
        )

        if checkpoint.checkpoint_type == "plan_review":
            artifact_store = ResearchArtifactStore(
                base_dir=self._outputs_dir_for_user(owner_user_id),
                db=db,
            )
            artifact_store.write_json(
                owner_user_id=owner_user_id,
                session_id=session_id,
                artifact_name="approved_plan.json",
                payload=merged_payload,
                phase="collecting",
                job_id=None,
            )

        db.update_phase(session_id, phase="collecting", status="queued")
        return db.attach_active_job(session_id, None)

    def build_package(
        self,
        *,
        owner_user_id: str,
        session_id: str,
        brief: dict[str, Any],
        outline: dict[str, Any],
        report_markdown: str,
        claims: list[dict[str, Any]],
        source_inventory: list[dict[str, Any]],
        unresolved_questions: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build and persist the final deep research package."""
        db = self._db_for_user(owner_user_id)
        session = db.get_session(session_id)
        if session is None:
            raise KeyError(session_id)

        package = build_final_package(
            brief=brief,
            outline=outline,
            report_markdown=report_markdown,
            claims=claims,
            source_inventory=source_inventory,
            unresolved_questions=unresolved_questions,
        )
        artifact_store = ResearchArtifactStore(
            base_dir=self._outputs_dir_for_user(owner_user_id),
            db=db,
        )
        artifact_store.write_json(
            owner_user_id=owner_user_id,
            session_id=session_id,
            artifact_name="bundle.json",
            payload=package,
            phase="packaging",
            job_id=None,
        )
        return package


__all__ = ["ResearchService"]
