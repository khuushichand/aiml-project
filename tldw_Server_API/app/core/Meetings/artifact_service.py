"""Artifact-level domain logic for Meetings."""

from __future__ import annotations

import re
from typing import Any

from tldw_Server_API.app.core.DB_Management.Meetings_DB import MeetingsDatabase

_DEFAULT_FINAL_KINDS: tuple[str, ...] = ("summary", "action_items", "decisions", "speaker_stats")


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

    def generate_final_artifacts(
        self,
        *,
        session_id: str,
        transcript_text: str,
        include: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        clean_transcript = str(transcript_text).strip()
        if not clean_transcript:
            raise ValueError("transcript_text is required")
        if self._db.get_session(session_id=session_id) is None:
            raise KeyError(f"meeting session not found: {session_id}")

        requested_kinds = include or list(_DEFAULT_FINAL_KINDS)
        payloads = self._build_finalize_payloads(clean_transcript)

        artifacts: list[dict[str, Any]] = []
        for kind in requested_kinds:
            normalized_kind = str(kind).strip().lower()
            if normalized_kind not in payloads:
                continue
            artifacts.append(
                self.create_artifact(
                    session_id=session_id,
                    kind=normalized_kind,
                    format="json",
                    payload_json=payloads[normalized_kind],
                )
            )
        return artifacts

    @staticmethod
    def _build_finalize_payloads(transcript_text: str) -> dict[str, dict[str, Any]]:
        summary = MeetingArtifactService._build_summary(transcript_text)
        action_items = MeetingArtifactService._extract_action_items(transcript_text)
        decisions = MeetingArtifactService._extract_decisions(transcript_text)
        speaker_stats = {
            "word_count": len([token for token in transcript_text.split() if token.strip()]),
            "line_count": len([line for line in transcript_text.splitlines() if line.strip()]),
        }
        return {
            "summary": {"text": summary},
            "action_items": {"items": action_items},
            "decisions": {"items": decisions},
            "speaker_stats": speaker_stats,
        }

    @staticmethod
    def _build_summary(transcript_text: str) -> str:
        collapsed = " ".join(part.strip() for part in transcript_text.splitlines() if part.strip())
        if len(collapsed) <= 240:
            return collapsed
        return f"{collapsed[:237].rstrip()}..."

    @staticmethod
    def _extract_action_items(transcript_text: str) -> list[str]:
        matches = re.findall(r"(?:^|\b)(?:TODO|ACTION)[:\-]\s*([^\.\n]+)", transcript_text, flags=re.IGNORECASE)
        items = [match.strip() for match in matches if match.strip()]
        if items:
            return items
        return []

    @staticmethod
    def _extract_decisions(transcript_text: str) -> list[str]:
        matches = re.findall(r"(?:^|\b)(?:DECISION|DECIDED)[:\-]\s*([^\.\n]+)", transcript_text, flags=re.IGNORECASE)
        decisions = [match.strip() for match in matches if match.strip()]
        if decisions:
            return decisions
        return []
