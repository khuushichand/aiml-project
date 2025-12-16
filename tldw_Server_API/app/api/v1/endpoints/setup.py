"""Setup endpoints for the first-time configuration flow."""

from __future__ import annotations

import inspect
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger

from tldw_Server_API.app.core.Setup import setup_manager
from tldw_Server_API.app.core.Setup import install_manager
from tldw_Server_API.app.core.Setup.install_manager import execute_install_plan
from tldw_Server_API.app.core.Setup.install_schema import InstallPlan
from tldw_Server_API.app.api.v1.API_Deps.setup_deps import require_local_setup_access
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    get_current_user,
    get_db_transaction,
    require_permissions,
    require_roles,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat

router = APIRouter(prefix="/setup", tags=["setup"], include_in_schema=True)


class ConfigUpdates(BaseModel):
    updates: dict[str, dict[str, Any]] = Field(
        ..., description="Mapping of section -> key/value pairs to persist in config.txt"
    )


class SetupCompleteRequest(BaseModel):
    disable_first_time_setup: Optional[bool] = Field(
        False,
        description="If true, flips enable_first_time_setup to false so the screen stays hidden",
    )
    install_plan: Optional[InstallPlan] = Field(
        None,
        description="Backend installation instructions to execute after setup completes.",
    )


class AssistantQuestion(BaseModel):
    question: str = Field(..., min_length=1, description="Natural language question for the setup assistant")


async def require_admin_and_system_configure(
    principal: AuthPrincipal = Depends(get_auth_principal),  # noqa: B008
) -> AuthPrincipal:
    """
    Combined dependency that enforces an admin-style principal and reuses the
    SYSTEM_CONFIGURE permission gate while resolving the AuthPrincipal once.

    Semantics:
    - Principals with ``is_admin=True`` are allowed regardless of an explicit
      SYSTEM_CONFIGURE grant (matching other admin surfaces).
    - Other principals must hold the ``admin`` role and the SYSTEM_CONFIGURE
      permission to pass.
    """
    role_checker = require_roles("admin")
    perm_checker = require_permissions(SYSTEM_CONFIGURE)

    principal = await role_checker(principal)
    principal = await perm_checker(principal)
    return principal


@router.get("/status", openapi_extra={"security": []})
async def get_setup_status(_guard: None = Depends(require_local_setup_access)) -> dict[str, Any]:
    """Return setup availability and placeholder diagnostics."""
    return setup_manager.get_status_snapshot()


@router.get("/config", openapi_extra={"security": []})
async def get_setup_config(_guard: None = Depends(require_local_setup_access)) -> dict[str, Any]:
    """Return the current configuration grouped by section for the setup UI."""
    status_snapshot = setup_manager.get_status_snapshot()
    if not status_snapshot["enabled"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Setup flow not enabled in config.txt")

    if not status_snapshot["needs_setup"]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Setup already completed. Toggle enable_first_time_setup to revisit the wizard.",
        )

    return setup_manager.get_config_snapshot()


@router.get("/install-status", openapi_extra={"security": []})
async def get_install_status(_guard: None = Depends(require_local_setup_access)) -> dict[str, Any]:
    """Return the current installation plan progress if available."""

    status_snapshot = setup_manager.get_status_snapshot()
    if not status_snapshot["enabled"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Setup flow not enabled in config.txt")

    install_status = install_manager.get_install_status_snapshot()
    if not install_status:
        return {"status": "idle"}

    return install_status


@router.post("/config", openapi_extra={"security": []})
async def update_setup_config(
    payload: ConfigUpdates,
    _guard: None = Depends(require_local_setup_access),
) -> dict[str, Any]:
    """Persist configuration updates coming from the setup UI."""
    status_snapshot = setup_manager.get_status_snapshot()
    if not status_snapshot["enabled"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Setup flow not enabled in config.txt")

    if not status_snapshot["needs_setup"]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Setup already completed. Toggle enable_first_time_setup to make changes here.",
        )

    try:
        backup_path = setup_manager.update_config(payload.updates)
        return {
            "success": True,
            "backup_path": str(backup_path) if backup_path else None,
            "requires_restart": True,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to write configuration via setup endpoint")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/complete", openapi_extra={"security": []})
async def mark_setup_complete(
    payload: SetupCompleteRequest,
    background_tasks: BackgroundTasks,
    _guard: None = Depends(require_local_setup_access),
) -> dict[str, Any]:
    """Mark the setup workflow as complete and optionally disable future prompts."""
    status_snapshot = setup_manager.get_status_snapshot()
    if not status_snapshot["enabled"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Setup flow not enabled in config.txt")

    if not status_snapshot["needs_setup"]:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Setup already marked as complete")

    setup_manager.mark_setup_completed(True)

    plan_requested = False
    if payload.install_plan and not payload.install_plan.is_empty():
        plan_requested = True
        plan_dict = model_dump_compat(payload.install_plan)
        background_tasks.add_task(execute_install_plan, plan_dict)

    if payload.disable_first_time_setup:
        setup_manager.update_config({setup_manager.SETUP_SECTION: {"enable_first_time_setup": False}}, create_backup=False)

    return {
        "success": True,
        "message": "Setup marked as complete. Restart the server to load new configuration.",
        "requires_restart": True,
        "install_plan_submitted": plan_requested,
    }


@router.post("/assistant", openapi_extra={"security": []})
async def ask_setup_assistant(
    payload: AssistantQuestion,
    _guard: None = Depends(require_local_setup_access),
) -> dict[str, Any]:
    """Provide contextual help for setup questions using local configuration knowledge."""
    try:
        return setup_manager.answer_setup_question(payload.question)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(

    "/reset",
    summary="Reset first-time setup flags (admin)",
    description=(
        "Admin-only recovery endpoint to re-enable the guided setup flow by setting "
        "enable_first_time_setup=true and setup_completed=false. Requires server restart."
    ),
)
async def reset_setup_flags(
    _principal: AuthPrincipal = Depends(require_admin_and_system_configure),  # noqa: B008
) -> dict[str, Any]:
    """Admin-only: reset first-time setup flags for recovery.

    Sets `enable_first_time_setup = true` and `setup_completed = false` in config.txt.
    """
    try:
        setup_manager.reset_setup_flags()
    except Exception as exc:
        logger.exception("Failed to reset setup flags")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "success": True,
        "message": "Setup flags reset. Restart the server and revisit /setup.",
        "requires_restart": True,
    }


@router.post(

    "/self-verify",
    summary="Mark current user as verified (initial setup)",
    description=(
        "Local-only helper to mark the authenticated user as verified during initial setup. "
        "Requires that the setup wizard is still enabled and not completed. Accepts either "
        "Bearer JWT (Authorization header) or X-API-KEY for multi-user SQLite setups."
    ),
)
async def setup_self_verify(
    current_user: dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db_transaction),
    _guard: None = Depends(require_local_setup_access),
) -> dict[str, Any]:
    """Mark the authenticated account as verified when setup is in progress."""
    status_snapshot = setup_manager.get_status_snapshot()
    if not status_snapshot["needs_setup"]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Self-verify is only available while initial setup is in progress.",
        )

    raw_id = current_user.get("id")
    try:
        user_id = int(raw_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Invalid user context",
        ) from exc
    if user_id <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid user context")

    raw_conn = getattr(db, "_conn", db)

    def _conn_module_name(conn: Any) -> str:
        module = getattr(conn.__class__, "__module__", "")
        return module or ""

    try:
        module_name = _conn_module_name(raw_conn)
        is_asyncpg = module_name.startswith("asyncpg")

        if is_asyncpg:
            await db.execute(
                "UPDATE users SET is_verified = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                True,
                user_id,
            )
        else:
            await db.execute(
                "UPDATE users SET is_verified = ?, updated_at = datetime('now') WHERE id = ?",
                (1, user_id),
            )
            # SQLite-style adapters should commit; Postgres path above does not
            commit = getattr(db, "commit", None)
            if callable(commit):
                result = commit()
                if inspect.isawaitable(result):
                    await result
            if raw_conn is not db:
                commit2 = getattr(raw_conn, "commit", None)
                if callable(commit2):
                    result2 = commit2()
                    if inspect.isawaitable(result2):
                        await result2
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to self-verify during setup")
        # Avoid leaking raw DB/driver errors to clients; keep detail generic.
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark account as verified; please try again.",
        ) from exc

    return {"success": True, "user_id": user_id, "message": "Account marked as verified."}
