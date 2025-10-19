"""
Webhook management endpoints extracted from evaluations_unified.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
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
from tldw_Server_API.app.core.Evaluations.webhook_manager import (
    WebhookManager,
    WebhookEvent,
    webhook_manager,
)
from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import (
    WebhookRegistrationRequest, WebhookRegistrationResponse,
    WebhookUpdateRequest, WebhookStatusResponse,
    WebhookTestRequest, WebhookTestResponse,
)


webhooks_router = APIRouter()


def _get_webhook_manager_for_user(user_id: int) -> WebhookManager:
    service = get_unified_evaluation_service_for_user(user_id)
    manager = getattr(service, "webhook_manager", None)
    if manager is None:
        setattr(service, "webhook_manager", webhook_manager)
        return webhook_manager
    return manager


def _normalize_webhook_status_record(record: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(record)
    status = normalized.get("status")
    if "active" not in normalized:
        normalized["active"] = True if status is None else status == "active"

    stats = normalized.get("statistics")
    if not isinstance(stats, dict):
        stats = {}

    total = stats.get("total_deliveries", normalized.pop("total_deliveries", 0)) or 0
    failed = stats.get("failed_deliveries", normalized.pop("failure_count", 0)) or 0
    success = stats.get("successful_deliveries", total - failed)
    stats.setdefault("total_deliveries", total)
    stats.setdefault("failed_deliveries", failed)
    stats.setdefault("successful_deliveries", success)
    stats.setdefault("success_rate", (success / total) if total else 0.0)
    normalized["statistics"] = stats

    if "created_at" not in normalized or normalized["created_at"] is None:
        normalized["created_at"] = datetime.now(timezone.utc)

    return normalized


@webhooks_router.post("/webhooks", response_model=WebhookRegistrationResponse)
async def register_webhook(
    request: WebhookRegistrationRequest,
    user_id: str = Depends(verify_api_key),
    current_user: User = Depends(get_request_user),
):
    try:
        wm = _get_webhook_manager_for_user(current_user.id)
        url = str(request.url)
        events = [WebhookEvent(e.value) if not isinstance(e, WebhookEvent) else e for e in request.events]
        result = await wm.register_webhook(
            user_id=user_id,
            url=url,
            secret=request.secret,
            events=events,
            retry_count=request.retry_count or 3,
            timeout_seconds=request.timeout_seconds or 30,
        )
        return WebhookRegistrationResponse(**result)
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
        _get_webhook_manager_for_user(current_user.id)
        records = await webhook_manager.get_webhook_status(user_id=user_id)
        normalized = [_normalize_webhook_status_record(w) for w in records]
        return [WebhookStatusResponse(**w) for w in normalized]
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
        await wm.unregister_webhook(user_id, webhook_id)
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
        _get_webhook_manager_for_user(current_user.id)
        result = await webhook_manager.test_webhook(user_id=user_id, url=str(payload.url))
        if isinstance(result, WebhookTestResponse):
            return result
        if isinstance(result, dict):
            return WebhookTestResponse(**result)
        return WebhookTestResponse(success=bool(result))
    except Exception as e:
        logger.error(f"Failed to test webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test webhook: {sanitize_error_message(e, 'webhook testing')}"
        )
