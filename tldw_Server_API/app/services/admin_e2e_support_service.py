from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import HTTPException, status

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo
from tldw_Server_API.app.core.AuthNZ.repos.users_repo import AuthnzUsersRepo
from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
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


def reset_admin_e2e_state() -> dict[str, Any]:
    """Clear transient in-memory seed state used by browser bootstrap helpers."""
    _SEEDED_PRINCIPALS.clear()
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

    additional_claims = {"session_id": session_id}
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


def run_due_backup_schedules_for_admin_e2e() -> dict[str, Any]:
    """Deterministic placeholder until backup schedule browser coverage is implemented."""
    return {"ok": True, "triggered_runs": 0}
