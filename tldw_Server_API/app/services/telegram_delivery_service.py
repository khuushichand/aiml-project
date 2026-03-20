from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tldw_Server_API.app.core.http_client import fetch
from tldw_Server_API.app.core.Jobs.manager import JobManager

_TELEGRAM_DELIVERY_NAMESPACE = uuid.UUID("8c8d4c1f-c899-4d13-819b-8178818ed020")


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_send_message_url(bot_token: str) -> str:
    return f"https://api.telegram.org/bot{bot_token}/sendMessage"


def _build_delivery_correlation_id(
    *,
    request_id: str,
    chat_id: int,
    text: str,
    message_thread_id: int | None = None,
    reply_to_message_id: int | None = None,
) -> str:
    material = json.dumps(
        {
            "request_id": request_id,
            "chat_id": chat_id,
            "text": text,
            "message_thread_id": message_thread_id,
            "reply_to_message_id": reply_to_message_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return str(uuid.uuid5(_TELEGRAM_DELIVERY_NAMESPACE, material))


def _extract_response_payload(response: Any) -> dict[str, Any] | None:
    if response is None or not hasattr(response, "json"):
        return None
    try:
        payload = response.json()
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


@dataclass(slots=True)
class TelegramDeliveryService:
    """Job handoff and outbound Telegram reply delivery helpers."""

    job_manager: JobManager | None = None
    transport: Callable[..., Any] = fetch

    async def queue_inbound_ask(
        self,
        *,
        owner_user_id: str,
        request_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if self.job_manager is None:
            raise ValueError("job_manager is required for inbound ask queueing")  # noqa: TRY003
        return await asyncio.to_thread(
            self.job_manager.create_job,
            domain="telegram",
            queue="default",
            job_type="telegram.ask",
            payload=payload,
            owner_user_id=owner_user_id,
            request_id=request_id,
            idempotency_key=request_id,
        )

    def send_message(
        self,
        *,
        bot_token: str,
        chat_id: int,
        text: str,
        request_id: str,
        message_thread_id: int | None = None,
        reply_to_message_id: int | None = None,
        parse_mode: str | None = None,
        disable_notification: bool = False,
        attempt: int = 1,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        correlation_id = _build_delivery_correlation_id(
            request_id=request_id,
            chat_id=chat_id,
            text=text,
            message_thread_id=message_thread_id,
            reply_to_message_id=reply_to_message_id,
        )
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if disable_notification:
            payload["disable_notification"] = True

        delivery_record = {
            "status": "failed",
            "delivery_correlation_id": correlation_id,
            "request_id": request_id,
            "attempt": max(1, _coerce_int(attempt) or 1),
            "chat_id": chat_id,
            "message_thread_id": message_thread_id,
            "reply_to_message_id": reply_to_message_id,
            "telegram_message_id": None,
            "status_code": None,
            "response_body": None,
        }
        try:
            response = self.transport(
                method="POST",
                url=_build_send_message_url(bot_token),
                json=payload,
                timeout=timeout,
            )
        except Exception as exc:
            delivery_record["error"] = str(exc)
            return delivery_record

        status_code = _coerce_int(getattr(response, "status_code", None))
        response_body = _extract_response_payload(response)
        telegram_message_id = None
        if isinstance(response_body, dict):
            result = response_body.get("result")
            if isinstance(result, dict):
                telegram_message_id = _coerce_int(result.get("message_id"))
        delivery_record["status_code"] = status_code
        delivery_record["response_body"] = response_body
        delivery_record["telegram_message_id"] = telegram_message_id
        if status_code is not None and 200 <= status_code < 300:
            delivery_record["status"] = "sent"
        return delivery_record
