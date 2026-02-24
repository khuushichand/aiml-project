"""Integration dispatch service for meeting sharing destinations."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.Meetings_DB import MeetingsDatabase
from tldw_Server_API.app.core.Security.egress import evaluate_url_policy

_SUPPORTED_INTEGRATIONS: tuple[str, ...] = ("slack", "webhook")


class MeetingIntegrationService:
    """Queue and shape outbound integration dispatches for meetings."""

    def __init__(self, db: MeetingsDatabase) -> None:
        self._db = db

    def queue_dispatch(
        self,
        *,
        session_id: str,
        integration_type: str,
        webhook_url: str,
        artifact_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        session = self._db.get_session(session_id=session_id)
        if session is None:
            raise KeyError(f"meeting session not found: {session_id}")

        normalized_integration = str(integration_type).strip().lower()
        if normalized_integration not in _SUPPORTED_INTEGRATIONS:
            raise ValueError(f"Unsupported integration type: {integration_type}")

        clean_webhook_url = str(webhook_url).strip()
        if not clean_webhook_url:
            raise ValueError("webhook_url is required")

        policy = evaluate_url_policy(clean_webhook_url)
        if not getattr(policy, "allowed", False):
            reason = str(getattr(policy, "reason", "") or "denied by policy")
            raise PermissionError(f"Webhook destination denied by policy: {reason}")

        selected_artifacts = self._resolve_artifacts(session_id=session_id, artifact_ids=artifact_ids or [])
        payload = self._build_dispatch_payload(
            integration_type=normalized_integration,
            webhook_url=clean_webhook_url,
            session_row=session,
            artifacts=selected_artifacts,
        )

        dispatch_id = self._db.record_integration_dispatch(
            session_id=session_id,
            integration_type=normalized_integration,
            status="queued",
            payload_json=payload,
            response_json=None,
            attempts=0,
            next_attempt_at=None,
            last_error=None,
        )
        row = self._db.get_integration_dispatch(dispatch_id=dispatch_id)
        if row is None:
            raise RuntimeError(f"Failed to fetch integration dispatch row: {dispatch_id}")
        return row

    def _resolve_artifacts(
        self,
        *,
        session_id: str,
        artifact_ids: list[str],
    ) -> list[dict[str, Any]]:
        if not artifact_ids:
            return self._db.list_artifacts(session_id=session_id)

        selected: list[dict[str, Any]] = []
        seen: set[str] = set()
        for artifact_id in artifact_ids:
            clean_artifact_id = str(artifact_id).strip()
            if not clean_artifact_id or clean_artifact_id in seen:
                continue
            seen.add(clean_artifact_id)
            artifact = self._db.get_artifact(artifact_id=clean_artifact_id)
            if artifact is None:
                raise ValueError(f"meeting artifact not found: {clean_artifact_id}")
            if str(artifact.get("session_id") or "") != str(session_id):
                raise ValueError(f"meeting artifact does not belong to session: {clean_artifact_id}")
            selected.append(artifact)
        return selected

    @staticmethod
    def _build_dispatch_payload(
        *,
        integration_type: str,
        webhook_url: str,
        session_row: dict[str, Any],
        artifacts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        session_payload = {
            "id": str(session_row.get("id") or ""),
            "title": str(session_row.get("title") or ""),
            "meeting_type": str(session_row.get("meeting_type") or ""),
            "status": str(session_row.get("status") or ""),
            "source_type": str(session_row.get("source_type") or ""),
            "language": session_row.get("language"),
            "created_at": session_row.get("created_at"),
            "updated_at": session_row.get("updated_at"),
        }
        artifacts_payload = [
            {
                "id": str(artifact.get("id") or ""),
                "kind": str(artifact.get("kind") or ""),
                "format": str(artifact.get("format") or ""),
                "payload_json": artifact.get("payload_json") or {},
                "version": int(artifact.get("version") or 1),
                "created_at": artifact.get("created_at"),
            }
            for artifact in artifacts
        ]
        generic_body = {
            "event": "meeting.artifacts.ready",
            "integration_type": integration_type,
            "session": session_payload,
            "artifacts": artifacts_payload,
        }
        request_body = (
            MeetingIntegrationService._build_slack_payload(session_payload, artifacts_payload)
            if integration_type == "slack"
            else generic_body
        )
        return {
            "integration_type": integration_type,
            "destination": {"url": webhook_url},
            "request_body": request_body,
            "metadata": {
                "session_id": session_payload["id"],
                "artifact_ids": [artifact["id"] for artifact in artifacts_payload],
                "artifact_count": len(artifacts_payload),
            },
        }

    @staticmethod
    def _build_slack_payload(session_row: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        title = str(session_row.get("title") or "Meeting")
        summary = MeetingIntegrationService._extract_summary(artifacts)
        action_items = MeetingIntegrationService._extract_action_items(artifacts)

        lines = [f"*Meeting Update:* {title}"]
        if summary:
            lines.append(f"*Summary:* {summary}")
        if action_items:
            lines.append("*Action Items:*")
            lines.extend(f"- {item}" for item in action_items[:8])

        return {"text": "\n".join(lines)}

    @staticmethod
    def _extract_summary(artifacts: list[dict[str, Any]]) -> str:
        for artifact in artifacts:
            if str(artifact.get("kind") or "") != "summary":
                continue
            payload = artifact.get("payload_json") or {}
            text = payload.get("text") if isinstance(payload, dict) else None
            if text:
                return str(text).strip()
        return ""

    @staticmethod
    def _extract_action_items(artifacts: list[dict[str, Any]]) -> list[str]:
        for artifact in artifacts:
            if str(artifact.get("kind") or "") != "action_items":
                continue
            payload = artifact.get("payload_json") or {}
            if not isinstance(payload, dict):
                continue
            items = payload.get("items") or []
            if not isinstance(items, list):
                continue
            clean_items = [str(item).strip() for item in items if str(item).strip()]
            if clean_items:
                return clean_items
        return []

