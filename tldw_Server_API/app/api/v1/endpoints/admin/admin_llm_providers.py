from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    LLMProviderOverrideListResponse,
    LLMProviderOverrideRequest,
    LLMProviderOverrideResponse,
    LLMProviderTestRequest,
    LLMProviderTestResponse,
)
from tldw_Server_API.app.services import admin_llm_providers_service

router = APIRouter()


def _get_ensure_sqlite_authnz_ready_if_test_mode():
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod

    return admin_mod._ensure_sqlite_authnz_ready_if_test_mode


@router.get(
    "/llm/providers/overrides",
    response_model=LLMProviderOverrideListResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_list_llm_provider_overrides(
    provider: str | None = Query(None),
) -> LLMProviderOverrideListResponse:
    await _get_ensure_sqlite_authnz_ready_if_test_mode()()
    return await admin_llm_providers_service.list_overrides(provider)


@router.get(
    "/llm/providers/overrides/{provider}",
    response_model=LLMProviderOverrideResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_get_llm_provider_override(provider: str) -> LLMProviderOverrideResponse:
    await _get_ensure_sqlite_authnz_ready_if_test_mode()()
    return await admin_llm_providers_service.get_override(provider)


@router.put(
    "/llm/providers/overrides/{provider}",
    response_model=LLMProviderOverrideResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_upsert_llm_provider_override(
    provider: str,
    payload: LLMProviderOverrideRequest,
) -> LLMProviderOverrideResponse:
    await _get_ensure_sqlite_authnz_ready_if_test_mode()()
    return await admin_llm_providers_service.upsert_override(provider, payload)


@router.delete(
    "/llm/providers/overrides/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_delete_llm_provider_override(provider: str) -> Response:
    await _get_ensure_sqlite_authnz_ready_if_test_mode()()
    await admin_llm_providers_service.delete_override(provider)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/llm/providers/test",
    response_model=LLMProviderTestResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_test_llm_provider(payload: LLMProviderTestRequest) -> LLMProviderTestResponse:
    return await admin_llm_providers_service.test_provider(payload)
