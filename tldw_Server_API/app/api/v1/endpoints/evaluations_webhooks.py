"""
Webhook management endpoints extracted from evaluations_unified.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from tldw_Server_API.app.api.v1.endpoints.evaluations_auth import (
    verify_api_key,
    create_error_response,
    sanitize_error_message,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import (
    get_unified_evaluation_service_for_user,
)
from tldw_Server_API.app.core.Evaluations.webhook_manager import WebhookManager, WebhookEvent
from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import (
    WebhookRegistrationRequest, WebhookRegistrationResponse,
    WebhookUpdateRequest, WebhookStatusResponse,
    WebhookTestRequest, WebhookTestResponse,
)


webhooks_router = APIRouter()


def _get_webhook_manager_for_user(user_id: int) -> WebhookManager:
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    db_path = str(DatabasePaths.get_evaluations_db_path(user_id))
    return WebhookManager(db_path=db_path)


@webhooks_router.post("/webhooks", response_model=WebhookRegistrationResponse)
async def register_webhook(
    request: WebhookRegistrationRequest,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        wm = _get_webhook_manager_for_user(current_user.id)
        webhook_id = wm.register_webhook(
            user_id=user_id,
            url=request.url,
            secret=request.secret,
            events=request.events,
            active=True,
            retry_count=request.retry_count or 3,
            timeout_seconds=request.timeout_seconds or 30,
        )
        return WebhookRegistrationResponse(webhook_id=webhook_id, status="registered")
    except Exception as e:
        logger.error(f"Failed to register webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register webhook: {sanitize_error_message(e, 'webhook registration')}"
        )


@webhooks_router.get("/webhooks", response_model=List[WebhookStatusResponse])
async def list_webhooks(
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        wm = _get_webhook_manager_for_user(current_user.id)
        return [WebhookStatusResponse(**w) for w in wm.list_webhooks(user_id)]
    except Exception as e:
        logger.error(f"Failed to list webhooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list webhooks: {sanitize_error_message(e, 'listing webhooks')}"
        )


@webhooks_router.delete("/webhooks")
async def unregister_webhook(
    webhook_id: str,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        wm = _get_webhook_manager_for_user(current_user.id)
        wm.unregister_webhook(user_id, webhook_id)
        return {"status": "unregistered", "webhook_id": webhook_id}
    except Exception as e:
        logger.error(f"Failed to unregister webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unregister webhook: {sanitize_error_message(e, 'webhook removal')}"
        )


@webhooks_router.post("/webhooks/test", response_model=WebhookTestResponse)
async def test_webhook(
    payload: WebhookTestRequest,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        wm = _get_webhook_manager_for_user(current_user.id)
        ok = await wm.send_webhook(
            user_id=user_id,
            event=WebhookEvent.EVALUATION_STARTED,
            evaluation_id="test",
            data=payload.data or {"message": "webhook test"}
        )
        return WebhookTestResponse(status="sent" if ok else "failed")
    except Exception as e:
        logger.error(f"Failed to test webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test webhook: {sanitize_error_message(e, 'webhook testing')}"
        )

