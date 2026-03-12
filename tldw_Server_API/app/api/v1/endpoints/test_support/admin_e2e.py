from __future__ import annotations

from fastapi import APIRouter

from tldw_Server_API.app.api.v1.schemas.test_support_schemas import (
    AdminE2EBootstrapJwtSessionRequest,
    AdminE2EBootstrapJwtSessionResponse,
    AdminE2EResetResponse,
    AdminE2ERunDueBackupSchedulesResponse,
    AdminE2ESeedRequest,
    AdminE2ESeedResponse,
)
from tldw_Server_API.app.services.admin_e2e_support_service import (
    bootstrap_admin_e2e_jwt_session,
    reset_admin_e2e_state,
    run_due_backup_schedules_for_admin_e2e,
    seed_admin_e2e_scenario,
)

router = APIRouter()


@router.post("/reset", response_model=AdminE2EResetResponse)
async def reset_admin_e2e() -> AdminE2EResetResponse:
    """Reset transient admin e2e seed state."""
    return AdminE2EResetResponse(**(await reset_admin_e2e_state()))


@router.post("/seed", response_model=AdminE2ESeedResponse)
async def seed_admin_e2e(request: AdminE2ESeedRequest) -> AdminE2ESeedResponse:
    """Seed deterministic AuthNZ fixtures for admin-ui real-backend browser tests."""
    payload = await seed_admin_e2e_scenario(request.scenario)
    return AdminE2ESeedResponse(**payload)


@router.post("/bootstrap-jwt-session", response_model=AdminE2EBootstrapJwtSessionResponse)
async def bootstrap_jwt_session(
    request: AdminE2EBootstrapJwtSessionRequest,
) -> AdminE2EBootstrapJwtSessionResponse:
    """Return browser cookie payloads for a seeded multi-user admin session."""
    payload = await bootstrap_admin_e2e_jwt_session(request.principal_key)
    return AdminE2EBootstrapJwtSessionResponse(**payload)


@router.post("/run-due-backup-schedules", response_model=AdminE2ERunDueBackupSchedulesResponse)
async def run_due_backup_schedules() -> AdminE2ERunDueBackupSchedulesResponse:
    """Trigger a deterministic scheduler tick for backup schedule browser tests."""
    return AdminE2ERunDueBackupSchedulesResponse(**(await run_due_backup_schedules_for_admin_e2e()))
