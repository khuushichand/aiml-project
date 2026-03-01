"""Template-level domain logic for Meetings."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from tldw_Server_API.app.core.DB_Management.Meetings_DB import MeetingsDatabase

_BUILTIN_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "id": "mtpl_builtin_default",
        "name": "General Meeting",
        "scope": "builtin",
        "enabled": 1,
        "is_default": 1,
        "version": 1,
        "schema_json": {
            "sections": ["summary", "decisions", "action_items", "risks"],
        },
        "created_at": None,
        "updated_at": None,
    },
    {
        "id": "mtpl_builtin_standup",
        "name": "Daily Standup",
        "scope": "builtin",
        "enabled": 1,
        "is_default": 0,
        "version": 1,
        "schema_json": {
            "sections": ["yesterday", "today", "blockers", "owners"],
        },
        "created_at": None,
        "updated_at": None,
    },
)


class MeetingTemplateService:
    """High-level operations for meeting templates."""

    def __init__(self, db: MeetingsDatabase) -> None:
        self._db = db

    @staticmethod
    def _clone_template(template: dict[str, Any]) -> dict[str, Any]:
        return deepcopy(template)

    @classmethod
    def _builtin_templates(cls, *, include_disabled: bool) -> list[dict[str, Any]]:
        rows = [cls._clone_template(row) for row in _BUILTIN_TEMPLATES]
        if include_disabled:
            return rows
        return [row for row in rows if int(row.get("enabled") or 0) > 0]

    def create_template(
        self,
        *,
        name: str,
        scope: str = "personal",
        schema_json: dict[str, Any],
        enabled: bool = True,
        is_default: bool = False,
    ) -> dict[str, Any]:
        normalized_scope = str(scope).strip().lower()
        if normalized_scope == "builtin":
            raise ValueError("builtin templates are read-only")
        template_id = self._db.create_template(
            name=name,
            scope=normalized_scope,
            schema_json=schema_json,
            enabled=enabled,
            is_default=is_default,
        )
        row = self._db.get_template(template_id=template_id)
        if row is None:
            raise RuntimeError(f"Failed to fetch created template: {template_id}")
        return row

    def get_template(self, *, template_id: str) -> dict[str, Any]:
        for builtin in _BUILTIN_TEMPLATES:
            if builtin["id"] == template_id:
                return self._clone_template(builtin)
        row = self._db.get_template(template_id=template_id)
        if row is None:
            raise KeyError(f"meeting template not found: {template_id}")
        return row

    def list_templates(
        self,
        *,
        scope: str | None = None,
        include_disabled: bool = False,
    ) -> list[dict[str, Any]]:
        normalized_scope = str(scope).strip().lower() if scope else None
        rows: list[dict[str, Any]] = []

        if normalized_scope in {None, "builtin"}:
            rows.extend(self._builtin_templates(include_disabled=include_disabled))

        if normalized_scope != "builtin":
            rows.extend(
                self._db.list_templates(
                    scope=normalized_scope,
                    enabled_only=not include_disabled,
                )
            )

        return rows
