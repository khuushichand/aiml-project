from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal, require_roles
from tldw_Server_API.app.api.v1.endpoints.telegram_support import (
    telegram_admin_get_bot_impl,
    telegram_admin_put_bot_impl,
    telegram_webhook_impl,
)
from tldw_Server_API.app.api.v1.schemas.telegram_schemas import (
    TelegramBotConfigResponse,
    TelegramBotConfigUpdate,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.put("/admin/bot", dependencies=[Depends(require_roles("admin"))], response_model=TelegramBotConfigResponse)
async def telegram_admin_put_bot(
    request: Request,
    payload: TelegramBotConfigUpdate,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> TelegramBotConfigResponse:
    return await telegram_admin_put_bot_impl(principal=principal, payload=payload, request=request)


@router.get("/admin/bot", dependencies=[Depends(require_roles("admin"))], response_model=TelegramBotConfigResponse)
async def telegram_admin_get_bot(
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> TelegramBotConfigResponse:
    return await telegram_admin_get_bot_impl(principal=principal, request=request)


@router.post("/webhook")
async def telegram_webhook(request: Request):
    return await telegram_webhook_impl(request=request)
