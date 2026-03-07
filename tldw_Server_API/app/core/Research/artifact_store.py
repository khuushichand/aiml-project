"""Helpers for writing internal deep research artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import (
    ResearchArtifactRow,
    ResearchSessionsDB,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import normalize_output_storage_filename


class ResearchArtifactStore:
    """Write internal artifacts to disk and register them in the research manifest."""

    def __init__(self, *, base_dir: str | Path, db: ResearchSessionsDB):
        self.base_dir = Path(base_dir)
        self.db = db

    def _artifact_path(self, session_id: str, artifact_name: str) -> Path:
        safe_name = normalize_output_storage_filename(
            artifact_name,
            allow_absolute=False,
            reject_relative_with_separators=True,
            expand_user=False,
        )
        artifact_dir = self.base_dir / "research" / session_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir / safe_name

    def _next_version(self, session_id: str, artifact_name: str) -> int:
        existing = [
            artifact.artifact_version
            for artifact in self.db.list_artifacts(session_id)
            if artifact.artifact_name == artifact_name
        ]
        return (max(existing) + 1) if existing else 1

    def write_json(
        self,
        *,
        owner_user_id: int | str,
        session_id: str,
        artifact_name: str,
        payload: dict[str, Any],
        phase: str,
        job_id: str | None,
    ) -> ResearchArtifactRow:
        _ = owner_user_id
        path = self._artifact_path(session_id, artifact_name)
        encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        path.write_bytes(encoded)
        return self.db.record_artifact(
            session_id=session_id,
            artifact_name=path.name,
            artifact_version=self._next_version(session_id, path.name),
            storage_path=str(path),
            content_type="application/json",
            byte_size=len(encoded),
            checksum=hashlib.sha256(encoded).hexdigest(),
            phase=phase,
            job_id=job_id,
        )
