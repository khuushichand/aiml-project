from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos.data_subject_requests_repo import (
    AuthnzDataSubjectRequestsRepo,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.services import admin_scope_service

_CATEGORY_DEFS: tuple[dict[str, str], ...] = (
    {"key": "media_records", "label": "Media records"},
    {"key": "chat_messages", "label": "Chat sessions/messages"},
    {"key": "notes", "label": "Notes"},
    {"key": "audit_events", "label": "Audit log events"},
)
_SUPPORTED_CATEGORY_KEYS = {entry["key"] for entry in _CATEGORY_DEFS}
_UNSUPPORTED_CATEGORY_KEYS = {"embeddings"}


def _normalize_identifier(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="requester_identifier_required",
        )
    return normalized


def _normalize_requested_categories(
    *,
    request_type: str | None,
    categories: list[str] | None,
) -> list[str]:
    if categories is None:
        if request_type == "erasure":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="categories_required",
            )
        return [entry["key"] for entry in _CATEGORY_DEFS]

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in categories:
        value = str(raw_value or "").strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)

    if request_type == "erasure" and not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="categories_required",
        )

    unsupported = [
        value
        for value in normalized
        if value not in _SUPPORTED_CATEGORY_KEYS
    ]
    if unsupported:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="unsupported_category",
        )

    return normalized


async def _resolve_requester_user(requester_identifier: str) -> dict[str, Any]:
    normalized = _normalize_identifier(requester_identifier)
    db_pool = await get_db_pool()

    row: dict[str, Any] | None = None
    if normalized.isdigit():
        row = await db_pool.fetchrow("SELECT * FROM users WHERE id = ?", int(normalized))
    if row is None and "@" in normalized:
        row = await db_pool.fetchrow(
            "SELECT * FROM users WHERE LOWER(email) = LOWER(?)",
            normalized,
        )
    if row is None:
        row = await db_pool.fetchrow(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?)",
            normalized,
        )
    if row is None and "-" in normalized:
        row = await db_pool.fetchrow("SELECT * FROM users WHERE uuid = ?", normalized)

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="requester_not_found",
        )

    try:
        row["id"] = int(row["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="requester_resolution_failed",
        ) from exc

    return row


def _sqlite_count(path: Path, query: str, params: tuple[Any, ...] = ()) -> int:
    if not path.exists():
        return 0
    try:
        with sqlite3.connect(path) as conn:
            row = conn.execute(query, params).fetchone()
    except sqlite3.Error as exc:
        logger.debug("DSR count query failed for {}: {}", path, exc)
        return 0
    return int(row[0] if row else 0)


def _count_media_records(user_id: int) -> int:
    return _sqlite_count(
        DatabasePaths.get_media_db_path(user_id),
        "SELECT COUNT(*) FROM Media WHERE deleted = 0 AND is_trash = 0",
    )


def _count_notes(user_id: int) -> int:
    return _sqlite_count(
        DatabasePaths.get_chacha_db_path(user_id),
        "SELECT COUNT(*) FROM notes WHERE deleted = 0",
    )


def _count_chat_messages(user_id: int) -> int:
    return _sqlite_count(
        DatabasePaths.get_chacha_db_path(user_id),
        """
        SELECT COUNT(1)
        FROM messages m
        JOIN conversations c ON m.conversation_id = c.id
        WHERE c.client_id = ? AND c.deleted = 0 AND m.deleted = 0
        """,
        (str(user_id),),
    )


def _count_audit_events(user_id: int) -> int:
    from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import _resolve_audit_storage_mode

    shared_mode = _resolve_audit_storage_mode() == "shared"
    path = (
        DatabasePaths.get_shared_audit_db_path()
        if shared_mode
        else DatabasePaths.get_audit_db_path(user_id)
    )
    if shared_mode:
        return _sqlite_count(
            path,
            "SELECT COUNT(*) FROM audit_events WHERE tenant_user_id = ?",
            (str(user_id),),
        )
    return _sqlite_count(path, "SELECT COUNT(*) FROM audit_events")


def _build_summary_for_user(
    *,
    user_id: int,
    selected_categories: list[str],
) -> list[dict[str, Any]]:
    count_map = {
        "media_records": _count_media_records(user_id),
        "chat_messages": _count_chat_messages(user_id),
        "notes": _count_notes(user_id),
        "audit_events": _count_audit_events(user_id),
    }
    return [
        {
            "key": entry["key"],
            "label": entry["label"],
            "count": int(count_map.get(entry["key"], 0)),
        }
        for entry in _CATEGORY_DEFS
        if entry["key"] in selected_categories
    ]


def _coverage_metadata(*, selected_categories: list[str]) -> dict[str, Any]:
    return {
        "supported_categories": [entry["key"] for entry in _CATEGORY_DEFS],
        "selected_categories": selected_categories,
        "unsupported_categories": sorted(_UNSUPPORTED_CATEGORY_KEYS),
        "unsupported_details": {
            "embeddings": "Milestone 1 does not include authoritative embedding counts.",
        },
    }


async def preview_data_subject_request(
    *,
    requester_identifier: str,
    request_type: str | None = None,
    categories: list[str] | None = None,
) -> dict[str, Any]:
    user = await _resolve_requester_user(requester_identifier)
    selected_categories = _normalize_requested_categories(
        request_type=request_type,
        categories=categories,
    )
    summary = _build_summary_for_user(
        user_id=int(user["id"]),
        selected_categories=selected_categories,
    )
    return {
        "requester_identifier": user.get("email") or user.get("username") or requester_identifier,
        "resolved_user_id": int(user["id"]),
        "request_type": request_type,
        "selected_categories": selected_categories,
        "summary": summary,
        "counts": {entry["key"]: entry["count"] for entry in summary},
        "coverage_metadata": _coverage_metadata(selected_categories=selected_categories),
    }


async def _normalize_requested_by_user_id(principal: AuthPrincipal) -> int | None:
    if getattr(principal, "user_id", None) is None:
        return None
    try:
        candidate = int(principal.user_id)
    except (TypeError, ValueError):
        return None

    db_pool = await get_db_pool()
    row = await db_pool.fetchrow("SELECT id FROM users WHERE id = ?", candidate)
    if row is None:
        return None
    return candidate


async def record_data_subject_request(
    *,
    principal: AuthPrincipal,
    client_request_id: str,
    requester_identifier: str,
    request_type: str,
    categories: list[str] | None,
    preview: dict[str, Any] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    if preview is None:
        preview = await preview_data_subject_request(
            requester_identifier=requester_identifier,
            request_type=request_type,
            categories=categories,
        )

    db_pool = await get_db_pool()
    repo = AuthnzDataSubjectRequestsRepo(db_pool=db_pool)
    await repo.ensure_schema()

    return await repo.create_or_get_request(
        client_request_id=str(client_request_id).strip(),
        requester_identifier=str(preview["requester_identifier"]),
        resolved_user_id=int(preview["resolved_user_id"]),
        request_type=request_type,
        status="recorded",
        selected_categories=list(preview["selected_categories"]),
        preview_summary=list(preview["summary"]),
        coverage_metadata=dict(preview["coverage_metadata"]),
        requested_by_user_id=await _normalize_requested_by_user_id(principal),
        notes=notes,
    )


async def list_data_subject_requests(
    principal: AuthPrincipal,
    *,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    db_pool = await get_db_pool()
    repo = AuthnzDataSubjectRequestsRepo(db_pool=db_pool)
    await repo.ensure_schema()

    if admin_scope_service.is_platform_admin(principal):
        return await repo.list_requests(limit=limit, offset=offset)

    org_ids = await admin_scope_service.get_admin_org_ids(principal)
    if org_ids is None:
        return await repo.list_requests(limit=limit, offset=offset)

    from tldw_Server_API.app.core.AuthNZ.repos.users_repo import AuthnzUsersRepo

    users_repo = await AuthnzUsersRepo.from_pool()
    scoped_users, _ = await users_repo.list_users(
        offset=0,
        limit=1000,
        org_ids=org_ids,
    )
    scoped_user_ids = [int(row["id"]) for row in scoped_users if row.get("id") is not None]
    if getattr(principal, "user_id", None) is not None:
        try:
            principal_user_id = int(principal.user_id)
        except (TypeError, ValueError):
            principal_user_id = None
        if principal_user_id is not None and principal_user_id not in scoped_user_ids:
            scoped_user_ids.append(principal_user_id)

    return await repo.list_requests(
        limit=limit,
        offset=offset,
        resolved_user_ids=scoped_user_ids,
    )
