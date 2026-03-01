from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    get_db_transaction,
)
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    RouterAnalyticsBreakdownsResponse,
    RouterAnalyticsGranularity,
    RouterAnalyticsMetaResponse,
    RouterAnalyticsQuotaResponse,
    RouterAnalyticsRange,
    RouterAnalyticsStatusResponse,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_router_analytics_service

router = APIRouter()


@router.get("/router-analytics/status", response_model=RouterAnalyticsStatusResponse)
async def get_router_analytics_status(
    range: RouterAnalyticsRange = Query("8h"),
    org_id: int | None = Query(None, ge=1),
    provider: str | None = Query(None),
    model: str | None = Query(None),
    token_id: int | None = Query(None, ge=1),
    granularity: RouterAnalyticsGranularity | None = Query(None),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RouterAnalyticsStatusResponse:
    return await admin_router_analytics_service.get_router_analytics_status(
        principal=principal,
        db=db,
        range_value=range,
        org_id=org_id,
        provider=provider,
        model=model,
        token_id=token_id,
        granularity=granularity,
    )


@router.get("/router-analytics/status/breakdowns", response_model=RouterAnalyticsBreakdownsResponse)
async def get_router_analytics_status_breakdowns(
    range: RouterAnalyticsRange = Query("8h"),
    org_id: int | None = Query(None, ge=1),
    provider: str | None = Query(None),
    model: str | None = Query(None),
    token_id: int | None = Query(None, ge=1),
    granularity: RouterAnalyticsGranularity | None = Query(None),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RouterAnalyticsBreakdownsResponse:
    return await admin_router_analytics_service.get_router_analytics_status_breakdowns(
        principal=principal,
        db=db,
        range_value=range,
        org_id=org_id,
        provider=provider,
        model=model,
        token_id=token_id,
        granularity=granularity,
    )


@router.get("/router-analytics/quota", response_model=RouterAnalyticsQuotaResponse)
async def get_router_analytics_quota(
    range: RouterAnalyticsRange = Query("8h"),
    org_id: int | None = Query(None, ge=1),
    provider: str | None = Query(None),
    model: str | None = Query(None),
    token_id: int | None = Query(None, ge=1),
    granularity: RouterAnalyticsGranularity | None = Query(None),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RouterAnalyticsQuotaResponse:
    return await admin_router_analytics_service.get_router_analytics_quota(
        principal=principal,
        db=db,
        range_value=range,
        org_id=org_id,
        provider=provider,
        model=model,
        token_id=token_id,
        granularity=granularity,
    )


@router.get("/router-analytics/meta", response_model=RouterAnalyticsMetaResponse)
async def get_router_analytics_meta(
    org_id: int | None = Query(None, ge=1),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RouterAnalyticsMetaResponse:
    return await admin_router_analytics_service.get_router_analytics_meta(
        principal=principal,
        db=db,
        org_id=org_id,
    )
