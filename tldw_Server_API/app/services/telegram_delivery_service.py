from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tldw_Server_API.app.core.Jobs.manager import JobManager


@dataclass(slots=True)
class TelegramDeliveryService:
    """Minimal Telegram delivery service wrapper for job-backed execution."""

    job_manager: JobManager

    def queue_inbound_ask(
        self,
        *,
        owner_user_id: str,
        request_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self.job_manager.create_job(
            domain="telegram",
            queue="default",
            job_type="telegram.ask",
            payload=payload,
            owner_user_id=owner_user_id,
            request_id=request_id,
            idempotency_key=request_id,
        )
