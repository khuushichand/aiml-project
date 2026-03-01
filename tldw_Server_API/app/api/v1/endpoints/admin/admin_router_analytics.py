from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    get_db_transaction,
)
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    RouterAnalyticsAccessResponse,
    RouterAnalyticsBreakdownsResponse,
    RouterAnalyticsConversationsResponse,
    RouterAnalyticsGranularity,
    RouterAnalyticsLogResponse,
    RouterAnalyticsMetaResponse,
    RouterAnalyticsModelsResponse,
    RouterAnalyticsNetworkResponse,
    RouterAnalyticsProvidersResponse,
    RouterAnalyticsQuotaResponse,
    RouterAnalyticsRange,
    RouterAnalyticsStatusResponse,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_router_analytics_service

router = APIRouter()


@dataclass(frozen=True)
class RouterAnalyticsQueryParams:
    range_value: RouterAnalyticsRange
    org_id: int | None
    provider: str | None
    model: str | None
    token_id: int | None
    granularity: RouterAnalyticsGranularity | None


def _get_router_analytics_query_params(
    range_value: RouterAnalyticsRange = Query("8h", alias="range"),
    org_id: int | None = Query(None, ge=1),
    provider: str | None = Query(None),
    model: str | None = Query(None),
    token_id: int | None = Query(None, ge=1),
    granularity: RouterAnalyticsGranularity | None = Query(None),
) -> RouterAnalyticsQueryParams:
    return RouterAnalyticsQueryParams(
        range_value=range_value,
        org_id=org_id,
        provider=provider,
        model=model,
        token_id=token_id,
        granularity=granularity,
    )


RouterAnalyticsQueryDep = Annotated[
    RouterAnalyticsQueryParams,
    Depends(_get_router_analytics_query_params),
]


@router.get("/router-analytics/status", response_model=RouterAnalyticsStatusResponse)
async def get_router_analytics_status(
    query: RouterAnalyticsQueryDep,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RouterAnalyticsStatusResponse:
    return await admin_router_analytics_service.get_router_analytics_status(
        principal=principal,
        db=db,
        range_value=query.range_value,
        org_id=query.org_id,
        provider=query.provider,
        model=query.model,
        token_id=query.token_id,
        granularity=query.granularity,
    )


@router.get("/router-analytics/status/breakdowns", response_model=RouterAnalyticsBreakdownsResponse)
async def get_router_analytics_status_breakdowns(
    query: RouterAnalyticsQueryDep,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RouterAnalyticsBreakdownsResponse:
    return await admin_router_analytics_service.get_router_analytics_status_breakdowns(
        principal=principal,
        db=db,
        range_value=query.range_value,
        org_id=query.org_id,
        provider=query.provider,
        model=query.model,
        token_id=query.token_id,
        granularity=query.granularity,
    )


@router.get("/router-analytics/quota", response_model=RouterAnalyticsQuotaResponse)
async def get_router_analytics_quota(
    query: RouterAnalyticsQueryDep,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RouterAnalyticsQuotaResponse:
    return await admin_router_analytics_service.get_router_analytics_quota(
        principal=principal,
        db=db,
        range_value=query.range_value,
        org_id=query.org_id,
        provider=query.provider,
        model=query.model,
        token_id=query.token_id,
        granularity=query.granularity,
    )


@router.get("/router-analytics/providers", response_model=RouterAnalyticsProvidersResponse)
async def get_router_analytics_providers(
    query: RouterAnalyticsQueryDep,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RouterAnalyticsProvidersResponse:
    return await admin_router_analytics_service.get_router_analytics_providers(
        principal=principal,
        db=db,
        range_value=query.range_value,
        org_id=query.org_id,
        provider=query.provider,
        model=query.model,
        token_id=query.token_id,
        granularity=query.granularity,
    )


@router.get("/router-analytics/access", response_model=RouterAnalyticsAccessResponse)
async def get_router_analytics_access(
    query: RouterAnalyticsQueryDep,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RouterAnalyticsAccessResponse:
    return await admin_router_analytics_service.get_router_analytics_access(
        principal=principal,
        db=db,
        range_value=query.range_value,
        org_id=query.org_id,
        provider=query.provider,
        model=query.model,
        token_id=query.token_id,
        granularity=query.granularity,
    )


@router.get("/router-analytics/network", response_model=RouterAnalyticsNetworkResponse)
async def get_router_analytics_network(
    query: RouterAnalyticsQueryDep,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RouterAnalyticsNetworkResponse:
    return await admin_router_analytics_service.get_router_analytics_network(
        principal=principal,
        db=db,
        range_value=query.range_value,
        org_id=query.org_id,
        provider=query.provider,
        model=query.model,
        token_id=query.token_id,
        granularity=query.granularity,
    )


@router.get("/router-analytics/models", response_model=RouterAnalyticsModelsResponse)
async def get_router_analytics_models(
    query: RouterAnalyticsQueryDep,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RouterAnalyticsModelsResponse:
    return await admin_router_analytics_service.get_router_analytics_models(
        principal=principal,
        db=db,
        range_value=query.range_value,
        org_id=query.org_id,
        provider=query.provider,
        model=query.model,
        token_id=query.token_id,
        granularity=query.granularity,
    )


@router.get("/router-analytics/conversations", response_model=RouterAnalyticsConversationsResponse)
async def get_router_analytics_conversations(
    query: RouterAnalyticsQueryDep,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RouterAnalyticsConversationsResponse:
    return await admin_router_analytics_service.get_router_analytics_conversations(
        principal=principal,
        db=db,
        range_value=query.range_value,
        org_id=query.org_id,
        provider=query.provider,
        model=query.model,
        token_id=query.token_id,
        granularity=query.granularity,
    )


@router.get("/router-analytics/log", response_model=RouterAnalyticsLogResponse)
async def get_router_analytics_log(
    query: RouterAnalyticsQueryDep,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RouterAnalyticsLogResponse:
    return await admin_router_analytics_service.get_router_analytics_log(
        principal=principal,
        db=db,
        range_value=query.range_value,
        org_id=query.org_id,
        provider=query.provider,
        model=query.model,
        token_id=query.token_id,
        granularity=query.granularity,
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
