from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    get_db_transaction,
)
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    LLMTopSpendersResponse,
    LLMUsageLogResponse,
    LLMUsageSummaryResponse,
    UsageDailyResponse,
    UsageTopResponse,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_usage_service

router = APIRouter()


@router.get("/usage/daily", response_model=UsageDailyResponse)
async def get_usage_daily(
    user_id: int | None = None,
    start: str | None = Query(None, description="YYYY-MM-DD inclusive"),
    end: str | None = Query(None, description="YYYY-MM-DD inclusive"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    org_id: int | None = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> UsageDailyResponse:
    return await admin_usage_service.get_usage_daily(
        principal=principal,
        db=db,
        user_id=user_id,
        start=start,
        end=end,
        page=page,
        limit=limit,
        org_id=org_id,
    )


@router.get("/usage/top", response_model=UsageTopResponse)
async def get_usage_top(
    start: str | None = Query(None, description="YYYY-MM-DD inclusive"),
    end: str | None = Query(None, description="YYYY-MM-DD inclusive"),
    limit: int = Query(10, ge=1, le=100),
    metric: str = Query("requests", pattern="^(requests|bytes_total|bytes_in_total|errors)$"),
    org_id: int | None = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> UsageTopResponse:
    return await admin_usage_service.get_usage_top(
        principal=principal,
        db=db,
        start=start,
        end=end,
        limit=limit,
        metric=metric,
        org_id=org_id,
    )


@router.post("/usage/aggregate")
async def run_usage_aggregate(day: str | None = Query(None, description="YYYY-MM-DD")) -> dict:
    return await admin_usage_service.run_usage_aggregate(day)


@router.get("/usage/daily/export.csv", response_class=PlainTextResponse)
async def export_usage_daily_csv(
    user_id: int | None = None,
    start: str | None = Query(None, description="YYYY-MM-DD inclusive"),
    end: str | None = Query(None, description="YYYY-MM-DD inclusive"),
    limit: int = Query(1000, ge=1, le=10000),
    filename: str | None = Query(None, description="Optional filename for Content-Disposition"),
    org_id: int | None = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> PlainTextResponse:
    content, default_filename = await admin_usage_service.export_usage_daily_csv(
        principal=principal,
        db=db,
        user_id=user_id,
        start=start,
        end=end,
        limit=limit,
        org_id=org_id,
    )
    resp = PlainTextResponse(content=content, media_type="text/csv")
    if not filename:
        filename = default_filename
    if filename:
        safe = filename.replace("\n", " ").replace("\r", " ").replace("\"", "_")
        resp.headers["Content-Disposition"] = f"attachment; filename=\"{safe}\""
    return resp


@router.get("/usage/top/export.csv", response_class=PlainTextResponse)
async def export_usage_top_csv(
    start: str | None = Query(None, description="YYYY-MM-DD inclusive"),
    end: str | None = Query(None, description="YYYY-MM-DD inclusive"),
    limit: int = Query(100, ge=1, le=10000),
    metric: str = Query("requests", pattern="^(requests|bytes_total|bytes_in_total|errors)$"),
    filename: str | None = Query(None, description="Optional filename for Content-Disposition"),
    org_id: int | None = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> PlainTextResponse:
    content, default_filename = await admin_usage_service.export_usage_top_csv(
        principal=principal,
        db=db,
        start=start,
        end=end,
        limit=limit,
        metric=metric,
        org_id=org_id,
    )
    resp = PlainTextResponse(content=content, media_type="text/csv")
    if not filename:
        filename = default_filename
    if filename:
        safe = filename.replace("\n", " ").replace("\r", " ").replace("\"", "_")
        resp.headers["Content-Disposition"] = f"attachment; filename=\"{safe}\""
    return resp


@router.post("/llm-usage/aggregate")
async def run_llm_usage_aggregate(day: str | None = Query(None, description="YYYY-MM-DD")) -> dict:
    return await admin_usage_service.run_llm_usage_aggregate(day)


@router.get("/llm-usage", response_model=LLMUsageLogResponse)
async def get_llm_usage(
    user_id: int | None = None,
    provider: str | None = None,
    model: str | None = None,
    operation: str | None = None,
    status_code: int | None = Query(None, alias="status"),
    start: str | None = Query(None, description="ISO timestamp inclusive"),
    end: str | None = Query(None, description="ISO timestamp inclusive"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    org_id: int | None = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> LLMUsageLogResponse:
    return await admin_usage_service.get_llm_usage(
        principal=principal,
        db=db,
        user_id=user_id,
        provider=provider,
        model=model,
        operation=operation,
        status_code=status_code,
        start=start,
        end=end,
        page=page,
        limit=limit,
        org_id=org_id,
    )


@router.get("/llm-usage/summary", response_model=LLMUsageSummaryResponse)
async def get_llm_usage_summary(
    start: str | None = Query(None, description="ISO timestamp inclusive"),
    end: str | None = Query(None, description="ISO timestamp inclusive"),
    group_by: str = Query("user", pattern="^(user|provider|model|operation|day)$"),
    org_id: int | None = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> LLMUsageSummaryResponse:
    return await admin_usage_service.get_llm_usage_summary(
        principal=principal,
        db=db,
        start=start,
        end=end,
        group_by=group_by,
        org_id=org_id,
    )


@router.get("/llm-usage/top-spenders", response_model=LLMTopSpendersResponse)
async def get_llm_top_spenders(
    start: str | None = Query(None, description="ISO timestamp inclusive"),
    end: str | None = Query(None, description="ISO timestamp inclusive"),
    limit: int = Query(10, ge=1, le=500),
    org_id: int | None = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> LLMTopSpendersResponse:
    return await admin_usage_service.get_llm_top_spenders(
        principal=principal,
        db=db,
        start=start,
        end=end,
        limit=limit,
        org_id=org_id,
    )


@router.get("/llm-usage/export.csv", response_class=PlainTextResponse)
async def export_llm_usage_csv(
    user_id: int | None = None,
    provider: str | None = None,
    model: str | None = None,
    operation: str | None = None,
    status_code: int | None = Query(None, alias="status"),
    start: str | None = Query(None, description="ISO timestamp inclusive"),
    end: str | None = Query(None, description="ISO timestamp inclusive"),
    limit: int = Query(1000, ge=1, le=10000),
    org_id: int | None = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> PlainTextResponse:
    content = await admin_usage_service.export_llm_usage_csv(
        principal=principal,
        db=db,
        user_id=user_id,
        provider=provider,
        model=model,
        operation=operation,
        status_code=status_code,
        start=start,
        end=end,
        limit=limit,
        org_id=org_id,
    )
    return PlainTextResponse(content=content, media_type="text/csv")
