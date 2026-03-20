from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_roles
from tldw_Server_API.app.api.v1.endpoints.telegram_support import (
    telegram_admin_get_bot_impl,
    telegram_admin_put_bot_impl,
)
from tldw_Server_API.app.api.v1.schemas.telegram_schemas import TelegramBotConfigUpdate
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.put("/admin/bot", dependencies=[Depends(require_roles("admin"))])
async def telegram_admin_put_bot(
    payload: TelegramBotConfigUpdate,
    user: User = Depends(get_request_user),
) -> dict[str, Any]:
    return await telegram_admin_put_bot_impl(user=user, payload=payload)


@router.get("/admin/bot", dependencies=[Depends(require_roles("admin"))])
async def telegram_admin_get_bot(
    user: User = Depends(get_request_user),
) -> dict[str, Any]:
    return await telegram_admin_get_bot_impl(user=user)
