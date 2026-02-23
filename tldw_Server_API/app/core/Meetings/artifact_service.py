"""Artifact-level domain logic for Meetings."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.Meetings_DB import MeetingsDatabase


class MeetingArtifactService:
    """High-level operations for meeting artifacts."""

    def __init__(self, db: MeetingsDatabase) -> None:
        self._db = db

    def create_artifact(
        self,
        *,
        session_id: str,
        kind: str,
        format: str,
        payload_json: dict[str, Any],
        version: int = 1,
    ) -> dict[str, Any]:
        artifact_id = self._db.create_artifact(
            session_id=session_id,
            kind=kind,
            format=format,
            payload_json=payload_json,
            version=version,
        )
        return self.get_artifact(artifact_id=artifact_id)

    def get_artifact(self, *, artifact_id: str) -> dict[str, Any]:
        row = self._db.get_artifact(artifact_id=artifact_id)
        if row is None:
            raise KeyError(f"meeting artifact not found: {artifact_id}")
        return row

    def list_artifacts(self, *, session_id: str) -> list[dict[str, Any]]:
        return self._db.list_artifacts(session_id=session_id)
