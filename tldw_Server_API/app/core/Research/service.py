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
        return db.attach_active_job(
            session.id,
            str(job_id) if job_id is not None else str(job.get("uuid") or ""),
        )


__all__ = ["ResearchService"]
