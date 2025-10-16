from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class JobRecord:
    id: int
    uuid: Optional[str]
    domain: str
    queue: str
    job_type: str
    owner_user_id: Optional[str]
    project_id: Optional[int]
    payload: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    status: str
    priority: int
    max_retries: int
    retry_count: int
    available_at: Optional[datetime]
    leased_until: Optional[datetime]
    lease_id: Optional[str]
    worker_id: Optional[str]
    acquired_at: Optional[datetime]
    error_message: Optional[str]
    error_code: Optional[str]
    error_class: Optional[str]
    error_stack: Optional[Dict[str, Any]]
    last_error: Optional[str]
    cancel_requested_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancellation_reason: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]
