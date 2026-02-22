from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    get_db_transaction,
)
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    OrgBudgetItem,
    OrgBudgetListResponse,
    OrgBudgetSelfUpdateRequest,
    OrgBudgetUpdateRequest,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_budgets_service

router = APIRouter()


@router.get("/budgets", response_model=OrgBudgetListResponse)
async def admin_list_budgets(
    org_id: int | None = Query(None, description="Restrict to a specific organization"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> OrgBudgetListResponse:
    return await admin_budgets_service.list_budgets(
        principal=principal,
        org_id=org_id,
        page=page,
        limit=limit,
        db=db,
    )


@router.post("/budgets", response_model=OrgBudgetItem)
async def admin_upsert_budget(
    payload: OrgBudgetUpdateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> OrgBudgetItem:
    return await admin_budgets_service.upsert_budget(
        payload=payload,
        request=request,
        principal=principal,
        db=db,
    )


@router.put("/budgets/{org_id}", response_model=OrgBudgetItem)
async def admin_update_budget_by_org_id(
    org_id: int,
    payload: OrgBudgetSelfUpdateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> OrgBudgetItem:
    update_payload = OrgBudgetUpdateRequest(
        org_id=org_id,
        budgets=payload.budgets,
        clear_budgets=payload.clear_budgets,
    )
    return await admin_budgets_service.upsert_budget(
        payload=update_payload,
        request=request,
        principal=principal,
        db=db,
    )
