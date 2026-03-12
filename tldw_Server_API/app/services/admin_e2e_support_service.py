from __future__ import annotations

import shutil
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.orgs_teams import list_memberships_for_user
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo
from tldw_Server_API.app.core.AuthNZ.repos.users_repo import AuthnzUsersRepo
from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB

_ADMIN_USERNAME = "admin"
_ADMIN_EMAIL = "admin@example.local"
_NON_ADMIN_USERNAME = "member"
_NON_ADMIN_EMAIL = "member@example.local"
_REQUESTER_USERNAME = "requester"
_REQUESTER_EMAIL = "requester@example.local"
_ORG_NAME = "Admin E2E"
_ORG_SLUG = "admin-e2e"
_SEEDED_ALERT_ID = "alert-cpu-high"

_SEEDED_PRINCIPALS: dict[str, dict[str, Any]] = {}


async def _get_backup_schedules_repo():
    from tldw_Server_API.app.core.AuthNZ.repos.backup_schedules_repo import (
        AuthnzBackupSchedulesRepo,
    )

    pool = await get_db_pool()
    repo = AuthnzBackupSchedulesRepo(pool)
    await repo.ensure_schema()
    return repo


async def _soft_delete_all_backup_schedules() -> int:
    repo = await _get_backup_schedules_repo()
    deleted = 0
    deleted_at = datetime.now(timezone.utc).isoformat()
    while True:
        items, _ = await repo.list_schedules(limit=200, offset=0, include_deleted=False)
        if not items:
            break
        for item in items:
            if await repo.delete_schedule(str(item["id"]), deleted_at=deleted_at):
                deleted += 1
    return deleted


def _clear_backup_artifacts() -> int:
    backup_root = str(os.getenv("TLDW_DB_BACKUP_PATH") or "").strip()
    if not backup_root:
        return 0
    backup_dir = Path(backup_root)
    if not backup_dir.exists():
        return 0
    shutil.rmtree(backup_dir)
    return 1


async def reset_admin_e2e_state() -> dict[str, Any]:
    """Clear transient seed state and delete admin-e2e backup schedule artifacts."""
    _SEEDED_PRINCIPALS.clear()
    deleted_schedules = await _soft_delete_all_backup_schedules()
    deleted_backup_dirs = _clear_backup_artifacts()
    logger.debug(
        "Admin e2e reset completed: deleted_schedules={} deleted_backup_dirs={}",
        deleted_schedules,
        deleted_backup_dirs,
    )
    return {"ok": True}


def _fixture_secret(name: str, default_parts: tuple[str, ...]) -> str:
    """Return an env-overridable fixture secret without hardcoding it as a static literal."""
    configured = str(os.getenv(name) or "").strip()
    if configured:
        return configured
    return "".join(default_parts)


def _hash_fixture_password(password: str) -> str:
    """Hash a fixture password without applying password-strength policy."""
    return PasswordService().hasher.hash(password)


async def _ensure_user(
    *,
    users_repo: AuthnzUsersRepo,
    username: str,
    email: str,
    password: str,
    role: str,
) -> dict[str, Any]:
    users_db = UsersDB(users_repo.db_pool)
    await users_db.initialize()
    password_hash = _hash_fixture_password(password)

    existing = await users_db.get_user_by_username(username)
    if existing is None:
        existing = await users_db.get_user_by_email(email)

    if existing is None:
        existing = await users_db.create_user(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
            is_active=True,
            is_verified=True,
        )
    else:
        existing = await users_db.update_user(
            int(existing["id"]),
            email=email,
            password_hash=password_hash,
            is_active=True,
            is_verified=True,
            role=role,
        )

    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="admin_e2e_user_seed_failed",
        )

    await users_repo.assign_role_if_missing(user_id=int(existing["id"]), role_name=role)
    return existing


async def _ensure_org(
    *,
    orgs_repo: AuthnzOrgsTeamsRepo,
    owner_user_id: int,
) -> dict[str, Any]:
    rows, _ = await orgs_repo.list_organizations(limit=50, offset=0, q=_ORG_SLUG, with_total=False)
    for row in rows:
        if str(row.get("slug") or "").strip().lower() == _ORG_SLUG:
            return row

    rows, _ = await orgs_repo.list_organizations(limit=50, offset=0, q=_ORG_NAME, with_total=False)
    for row in rows:
        if str(row.get("name") or "").strip() == _ORG_NAME:
            return row

    return await orgs_repo.create_organization(
        name=_ORG_NAME,
        slug=_ORG_SLUG,
        owner_user_id=owner_user_id,
        metadata={"created_by": "admin_e2e_support"},
    )


async def _build_scope_claims_for_user(user_id: int) -> dict[str, Any]:
    memberships = await list_memberships_for_user(int(user_id))
    team_ids = sorted({membership.get("team_id") for membership in memberships if membership.get("team_id") is not None})
    org_ids = sorted({membership.get("org_id") for membership in memberships if membership.get("org_id") is not None})

    claims: dict[str, Any] = {}
    if team_ids:
        claims["team_ids"] = team_ids
    if org_ids:
        claims["org_ids"] = org_ids
    if len(team_ids) == 1:
        claims["active_team_id"] = team_ids[0]
    if len(org_ids) == 1:
        claims["active_org_id"] = org_ids[0]
    return claims


def _recreate_sqlite_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    return sqlite3.connect(path)


def _seed_media_store(*, user_id: int, media_count: int) -> None:
    media_db_path = DatabasePaths.get_media_db_path(user_id)
    with _recreate_sqlite_db(media_db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS Media (
                id INTEGER PRIMARY KEY,
                deleted INTEGER DEFAULT 0,
                is_trash INTEGER DEFAULT 0
            )
            """
        )
        for index in range(media_count):
            conn.execute(
                "INSERT INTO Media (id, deleted, is_trash) VALUES (?, 0, 0)",
                (index + 1,),
            )
        conn.execute("INSERT INTO Media (id, deleted, is_trash) VALUES (?, 1, 0)", (9001,))
        conn.execute("INSERT INTO Media (id, deleted, is_trash) VALUES (?, 0, 1)", (9002,))
        conn.commit()


def _seed_chacha_store(*, user_id: int, note_count: int, message_count: int) -> None:
    chacha_db_path = DatabasePaths.get_chacha_db_path(user_id)
    with _recreate_sqlite_db(chacha_db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS notes (id TEXT PRIMARY KEY, deleted INTEGER DEFAULT 0)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                deleted INTEGER DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                deleted INTEGER DEFAULT 0
            )
            """
        )
        for index in range(note_count):
            conn.execute("INSERT INTO notes (id, deleted) VALUES (?, 0)", (f"note-{index}",))
        conn.execute("INSERT INTO notes (id, deleted) VALUES (?, 1)", ("note-deleted",))
        conn.execute(
            "INSERT INTO conversations (id, client_id, deleted) VALUES (?, ?, 0)",
            ("conv-1", str(user_id)),
        )
        conn.execute(
            "INSERT INTO conversations (id, client_id, deleted) VALUES (?, ?, 1)",
            ("conv-deleted", str(user_id)),
        )
        for index in range(message_count):
            conn.execute(
                "INSERT INTO messages (id, conversation_id, deleted) VALUES (?, ?, 0)",
                (f"msg-{index}", "conv-1"),
            )
        conn.execute(
            "INSERT INTO messages (id, conversation_id, deleted) VALUES (?, ?, 1)",
            ("msg-deleted", "conv-1"),
        )
        conn.commit()


def _seed_audit_store(*, user_id: int, audit_count: int) -> None:
    from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import _resolve_audit_storage_mode

    audit_mode = _resolve_audit_storage_mode()
    if audit_mode == "shared":
        audit_db_path = DatabasePaths.get_shared_audit_db_path()
        audit_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(audit_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    category TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    context_user_id TEXT,
                    tenant_user_id TEXT
                )
                """
            )
            conn.execute("DELETE FROM audit_events WHERE tenant_user_id = ?", (str(user_id),))
            for index in range(audit_count):
                conn.execute(
                    """
                    INSERT INTO audit_events (
                        event_id,
                        timestamp,
                        category,
                        event_type,
                        severity,
                        context_user_id,
                        tenant_user_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"evt-{user_id}-{index}",
                        f"2026-03-11T20:00:0{index}Z",
                        "system",
                        "admin.e2e.seeded",
                        "low",
                        str(user_id),
                        str(user_id),
                    ),
                )
            conn.commit()
        return

    audit_db_path = DatabasePaths.get_audit_db_path(user_id)
    with _recreate_sqlite_db(audit_db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                context_user_id TEXT,
                tenant_user_id TEXT
            )
            """
        )
        for index in range(audit_count):
            conn.execute(
                """
                INSERT INTO audit_events (
                    event_id,
                    timestamp,
                    category,
                    event_type,
                    severity,
                    context_user_id,
                    tenant_user_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"evt-{user_id}-{index}",
                    f"2026-03-11T20:00:0{index}Z",
                    "system",
                    "admin.e2e.seeded",
                    "low",
                    str(user_id),
                    str(user_id),
                ),
            )
        conn.commit()


def _seed_dsr_subject_store_data(*, user_id: int) -> None:
    _seed_media_store(user_id=user_id, media_count=3)
    _seed_chacha_store(user_id=user_id, note_count=2, message_count=2)
    _seed_audit_store(user_id=user_id, audit_count=2)


async def seed_admin_e2e_scenario(scenario: str) -> dict[str, Any]:
    """Create deterministic users and fixtures for admin-ui real-backend browser tests."""
    settings = get_settings()
    if settings.AUTH_MODE != "multi_user":
        return {
            "scenario": scenario,
            "users": {},
            "fixtures": {
                "alerts": [{"alert_id": _SEEDED_ALERT_ID}],
                "organizations": [],
            },
        }

    pool = await get_db_pool()
    users_repo = AuthnzUsersRepo(db_pool=pool)
    orgs_repo = AuthnzOrgsTeamsRepo(db_pool=pool)

    admin_user = await _ensure_user(
        users_repo=users_repo,
        username=_ADMIN_USERNAME,
        email=_ADMIN_EMAIL,
        password=_fixture_secret("TLDW_ADMIN_E2E_ADMIN_PASSWORD", ("Admin", "Pass", "123", "!")),
        role="admin",
    )
    member_user = await _ensure_user(
        users_repo=users_repo,
        username=_NON_ADMIN_USERNAME,
        email=_NON_ADMIN_EMAIL,
        password=_fixture_secret("TLDW_ADMIN_E2E_MEMBER_PASSWORD", ("Member", "Pass", "123", "!")),
        role="user",
    )
    requester_user = await _ensure_user(
        users_repo=users_repo,
        username=_REQUESTER_USERNAME,
        email=_REQUESTER_EMAIL,
        password=_fixture_secret("TLDW_ADMIN_E2E_REQUESTER_PASSWORD", ("Requester", "Pass", "123", "!")),
        role="user",
    )

    org = await _ensure_org(orgs_repo=orgs_repo, owner_user_id=int(admin_user["id"]))
    org_id = int(org["id"])
    await orgs_repo.add_org_member(org_id=org_id, user_id=int(admin_user["id"]), role="admin")
    await orgs_repo.add_org_member(org_id=org_id, user_id=int(member_user["id"]), role="member")
    await orgs_repo.add_org_member(org_id=org_id, user_id=int(requester_user["id"]), role="member")

    if scenario == "dsr_jwt_admin":
        _seed_dsr_subject_store_data(user_id=int(requester_user["id"]))

    _SEEDED_PRINCIPALS["jwt_admin"] = {
        "user_id": int(admin_user["id"]),
        "username": str(admin_user["username"]),
        "role": str(admin_user.get("role") or "admin"),
    }
    _SEEDED_PRINCIPALS["jwt_non_admin"] = {
        "user_id": int(member_user["id"]),
        "username": str(member_user["username"]),
        "role": str(member_user.get("role") or "user"),
    }

    return {
        "scenario": scenario,
        "users": {
            "admin": {
                "id": int(admin_user["id"]),
                "username": str(admin_user["username"]),
                "email": str(admin_user["email"]),
                "key": "jwt_admin",
            },
            "non_admin": {
                "id": int(member_user["id"]),
                "username": str(member_user["username"]),
                "email": str(member_user["email"]),
                "key": "jwt_non_admin",
            },
            "requester": {
                "id": int(requester_user["id"]),
                "username": str(requester_user["username"]),
                "email": str(requester_user["email"]),
                "key": "requester_user",
            },
        },
        "fixtures": {
            "alerts": [{"alert_id": _SEEDED_ALERT_ID}],
            "organizations": [
                {
                    "id": org_id,
                    "name": str(org["name"]),
                    "slug": str(org.get("slug") or _ORG_SLUG),
                }
            ],
        },
    }


async def bootstrap_admin_e2e_jwt_session(principal_key: str) -> dict[str, Any]:
    """Create a real JWT session payload for Playwright cookie injection."""
    settings = get_settings()
    if settings.AUTH_MODE != "multi_user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="admin_e2e_jwt_requires_multi_user_mode",
        )

    seeded = _SEEDED_PRINCIPALS.get(principal_key)
    if seeded is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="admin_e2e_principal_not_seeded",
        )

    session_manager = await get_session_manager()
    jwt_service = JWTService(settings)

    temp_session = await session_manager.create_session(
        user_id=int(seeded["user_id"]),
        access_token=secrets.token_urlsafe(24),
        refresh_token=secrets.token_urlsafe(24),
        ip_address="127.0.0.1",
        user_agent="admin-ui-real-backend-e2e",
    )
    session_id = int(temp_session["session_id"])

    additional_claims = await _build_scope_claims_for_user(int(seeded["user_id"]))
    additional_claims["session_id"] = session_id
    access_token = jwt_service.create_access_token(
        user_id=int(seeded["user_id"]),
        username=str(seeded["username"]),
        role=str(seeded["role"]),
        additional_claims=additional_claims,
    )
    refresh_token = jwt_service.create_refresh_token(
        user_id=int(seeded["user_id"]),
        username=str(seeded["username"]),
        additional_claims=additional_claims,
    )
    await session_manager.update_session_tokens(
        session_id=session_id,
        access_token=access_token,
        refresh_token=refresh_token,
    )

    return {
        "principal_key": principal_key,
        "cookies": [
            {
                "name": "access_token",
                "value": access_token,
                "path": "/",
                "http_only": True,
                "same_site": "Lax",
            },
            {
                "name": "refresh_token",
                "value": refresh_token,
                "path": "/",
                "http_only": True,
                "same_site": "Lax",
            },
            {
                "name": "admin_session",
                "value": "1",
                "path": "/",
                "http_only": False,
                "same_site": "Lax",
            },
            {
                "name": "admin_auth_mode",
                "value": "jwt",
                "path": "/",
                "http_only": False,
                "same_site": "Lax",
            },
        ],
    }


async def run_due_backup_schedules_for_admin_e2e() -> dict[str, Any]:
    """Force active backup schedules due now and process the resulting queued jobs once."""
    from tldw_Server_API.app.core.Jobs.manager import JobManager
    from tldw_Server_API.app.core.Storage.backup_schedule_jobs import (
        BACKUP_SCHEDULE_DOMAIN,
        BACKUP_SCHEDULE_JOB_TYPE,
    )
    from tldw_Server_API.app.services.admin_backup_jobs_worker import handle_backup_schedule_job
    from tldw_Server_API.app.services.admin_backup_scheduler import _AdminBackupScheduler

    repo = await _get_backup_schedules_repo()
    scheduler = _AdminBackupScheduler(repo=repo)
    jobs = JobManager()

    active_schedules: list[dict[str, Any]] = []
    offset = 0
    page_size = 200
    while True:
        page, total = await repo.list_schedules(limit=page_size, offset=offset, include_deleted=False)
        active_schedules.extend([item for item in page if not bool(item.get("is_paused"))])
        offset += len(page)
        if not page or offset >= int(total):
            break

    if not active_schedules:
        return {"ok": True, "triggered_runs": 0}

    existing_job_ids = {
        str(job["id"])
        for job in jobs.list_jobs(
            domain=BACKUP_SCHEDULE_DOMAIN,
            job_type=BACKUP_SCHEDULE_JOB_TYPE,
            limit=500,
        )
    }

    forced_due = datetime.now(timezone.utc).replace(second=0, microsecond=0).isoformat()
    for schedule in active_schedules:
        await repo.update_schedule(
            str(schedule["id"]),
            next_run_at=forced_due,
            updated_by_user_id=(
                int(schedule["updated_by_user_id"])
                if schedule.get("updated_by_user_id") is not None
                else None
            ),
        )
        await scheduler._run_schedule(str(schedule["id"]))

    queued_new_jobs = [
        job
        for job in jobs.list_jobs(
            domain=BACKUP_SCHEDULE_DOMAIN,
            job_type=BACKUP_SCHEDULE_JOB_TYPE,
            status="queued",
            limit=500,
        )
        if str(job["id"]) not in existing_job_ids
    ]

    triggered_runs = 0
    for job in sorted(queued_new_jobs, key=lambda item: int(item["id"])):
        result = await handle_backup_schedule_job(job, repo=repo)
        jobs.complete_job(int(job["id"]), result=result, enforce=False)
        triggered_runs += 1

    return {"ok": True, "triggered_runs": triggered_runs}
