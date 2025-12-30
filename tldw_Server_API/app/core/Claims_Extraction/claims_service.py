from __future__ import annotations

import asyncio
import csv
import html
import io
import json
import math
import random
import threading
import time
import socket
import ssl
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import HTTPException, status
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, is_postgres_backend
from tldw_Server_API.app.core.AuthNZ.permissions import (
    CLAIMS_ADMIN,
    CLAIMS_REVIEW,
    SYSTEM_CONFIGURE,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo
from tldw_Server_API.app.core.Claims_Extraction.claims_rebuild_service import get_claims_rebuild_service
from tldw_Server_API.app.core.Claims_Extraction.monitoring import (
    record_claims_alert_email_delivery,
    record_claims_review_metrics,
    record_claims_webhook_delivery,
)
from tldw_Server_API.app.core.Claims_Extraction.claims_clustering import rebuild_claim_clusters_embeddings
from tldw_Server_API.app.core.Claims_Extraction.claims_embeddings import claim_embedding_id
from tldw_Server_API.app.core.Claims_Extraction.claims_notifications import (
    dispatch_claim_review_notifications,
    record_watchlist_cluster_notifications,
)
from tldw_Server_API.app.core.Claims_Extraction.span_alignment import find_text_span
from tldw_Server_API.app.core.DB_Management.DB_Manager import create_media_database
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.db_path_utils import get_user_media_db_path
from tldw_Server_API.app.core.Setup import setup_manager
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.exceptions import EgressPolicyError, RetryExhaustedError


_ROLE_HIERARCHY = {
    "owner": 4,
    "admin": 3,
    "lead": 2,
    "member": 1,
}
_ACTIVE_MEMBERSHIP_STATUSES = {"active"}
_REVIEW_TRANSITIONS = {
    "pending": {"approved", "flagged", "rejected", "reassigned"},
    "reassigned": {"pending", "approved", "flagged", "rejected"},
    "flagged": {"pending", "approved", "rejected"},
    "rejected": {"pending"},
    "approved": {"pending"},
}


def _role_at_least(user_role: str, required_role: str) -> bool:
    user_level = _ROLE_HIERARCHY.get(str(user_role).lower(), 0)
    required_level = _ROLE_HIERARCHY.get(str(required_role).lower(), 0)
    return user_level >= required_level


def _is_membership_active(membership: Optional[dict]) -> bool:
    if not membership:
        return False
    status_val = membership.get("status")
    if status_val is None:
        return False
    return str(status_val).strip().lower() in _ACTIVE_MEMBERSHIP_STATUSES


def _is_review_transition_allowed(current_status: str, new_status: str) -> bool:
    """Return True when a review status transition is allowed."""
    return new_status in _REVIEW_TRANSITIONS.get(current_status, {new_status})


def _normalize_claim_row(row: Dict[str, Any]) -> Dict[str, Any]:
    row.pop("media_owner_user_id", None)
    row.pop("media_client_id", None)
    return row


def _normalize_search_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    try:
        cluster_id = normalized.get("claim_cluster_id")
        normalized["claim_cluster_id"] = int(cluster_id) if cluster_id is not None else None
    except Exception:
        normalized["claim_cluster_id"] = None
    try:
        score = normalized.get("relevance_score")
        normalized["relevance_score"] = float(score) if score is not None else None
    except Exception:
        normalized["relevance_score"] = None
    return normalized


def _parse_email_recipients(raw_value: Optional[str]) -> List[str]:
    if raw_value is None:
        return []
    text = str(raw_value).strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
        if isinstance(payload, list):
            return [str(v).strip() for v in payload if str(v).strip()]
    except Exception:
        pass
    return [item.strip() for item in text.split(",") if item.strip()]


def _normalize_channels(raw_value: Optional[Any]) -> Dict[str, bool]:
    if isinstance(raw_value, dict):
        data = raw_value
    else:
        data = {}
        if raw_value:
            try:
                data = json.loads(str(raw_value))
            except Exception:
                data = {}
    return {
        "slack": bool(data.get("slack")),
        "webhook": bool(data.get("webhook")),
        "email": bool(data.get("email")),
    }


def _normalize_alert_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    normalized["email_recipients"] = _parse_email_recipients(row.get("email_recipients"))
    normalized["channels"] = _normalize_channels(
        row.get("channels_json") or row.get("channels")
    )
    normalized.pop("channels_json", None)
    if not normalized.get("name"):
        normalized["name"] = f"Legacy alert {row.get('id')}"
    if not normalized.get("alert_type"):
        normalized["alert_type"] = "threshold_breach"
    return normalized


def _normalize_review_rule(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    raw = normalized.get("predicate_json")
    try:
        normalized["predicate_json"] = json.loads(raw) if raw else {}
    except Exception:
        normalized["predicate_json"] = {}
    return normalized


def _normalize_notification_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    raw = normalized.get("payload_json")
    try:
        normalized["payload"] = json.loads(raw) if raw else {}
    except Exception:
        normalized["payload"] = {}
    normalized.pop("payload_json", None)
    return normalized


def _normalize_monitoring_event_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    raw = normalized.get("payload_json")
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {}
    normalized["payload"] = payload
    normalized.pop("payload_json", None)
    return normalized


def _normalize_review_extractor_metrics_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    raw = normalized.get("reason_code_counts_json")
    reason_payload: Dict[str, int] = {}
    if raw:
        try:
            parsed = json.loads(str(raw))
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    try:
                        reason_payload[str(key)] = int(value)
                    except Exception:
                        continue
        except Exception:
            reason_payload = {}
    normalized["reason_code_counts"] = reason_payload
    normalized.pop("reason_code_counts_json", None)
    return normalized


def _filter_monitoring_events_by_payload(
    events: List[Dict[str, Any]],
    *,
    provider: Optional[str],
    model: Optional[str],
) -> List[Dict[str, Any]]:
    if not provider and not model:
        return events
    filtered: List[Dict[str, Any]] = []
    for event in events:
        payload = event.get("payload") or {}
        if provider and str(payload.get("provider")) != str(provider):
            continue
        if model and str(payload.get("model")) != str(model):
            continue
        filtered.append(event)
    return filtered


def _get_watchlists_db(user_id: str) -> Optional[WatchlistsDatabase]:
    try:
        return WatchlistsDatabase.for_user(user_id=int(user_id))
    except Exception:
        return None


def _load_watchlist_cluster_counts(user_id: str, cluster_ids: Optional[List[int]] = None) -> Dict[int, int]:
    watch_db = _get_watchlists_db(user_id)
    if not watch_db:
        return {}
    try:
        return watch_db.list_watchlist_cluster_counts(cluster_ids=cluster_ids)
    except Exception:
        return {}


def _extract_request_metadata(request: Any) -> tuple[Optional[str], Optional[str]]:
    """Extract IP and user-agent for audit logging."""
    action_ip = None
    action_user_agent = None
    if request is None:
        return action_ip, action_user_agent
    try:
        if request.client:
            action_ip = request.client.host
    except Exception:
        action_ip = None
    try:
        action_user_agent = request.headers.get("user-agent")
    except Exception:
        action_user_agent = None
    return action_ip, action_user_agent


def _resolve_claim_owner_user_id(claim_row: Dict[str, Any], fallback_user_id: Optional[int]) -> str:
    owner_user_id = claim_row.get("media_owner_user_id")
    if owner_user_id is None:
        owner_user_id = claim_row.get("media_client_id")
    if owner_user_id is None:
        owner_user_id = fallback_user_id
    return str(owner_user_id) if owner_user_id is not None else ""


def _resolve_corrected_claim_span(
    target_db: MediaDatabase,
    claim_row: Dict[str, Any],
    corrected_text: str,
) -> tuple[Optional[int], Optional[int]]:
    try:
        media_id = int(claim_row.get("media_id") or 0)
        chunk_index = int(claim_row.get("chunk_index") or 0)
    except Exception:
        return (None, None)
    if media_id <= 0:
        return (None, None)
    chunk_row = target_db.get_unvectorized_chunk_by_index(media_id, chunk_index)
    if not chunk_row:
        return (None, None)
    chunk_text = chunk_row.get("chunk_text")
    if not chunk_text:
        return (None, None)
    span = find_text_span(str(chunk_text), str(corrected_text))
    if span is None:
        return (None, None)
    span_start, span_end = span
    start_char = chunk_row.get("start_char")
    if start_char is not None:
        try:
            offset = int(start_char)
            span_start += offset
            span_end += offset
        except Exception:
            pass
    return (span_start, span_end)


def _get_email_service():
    from tldw_Server_API.app.core.AuthNZ.email_service import get_email_service

    return get_email_service()


def _enqueue_claim_rebuild_if_needed(*, media_id: int, db_path: str) -> None:
    """Best-effort enqueue of a claims rebuild task for a media item."""
    try:
        svc = get_claims_rebuild_service()
        svc.submit(media_id=int(media_id), db_path=str(db_path))
    except Exception:
        pass


def _format_ratio(value: Optional[float]) -> str:
    """Return a human-friendly ratio string for alert messages."""
    if value is None:
        return "n/a"
    try:
        return f"{float(value) * 100:.2f}%"
    except Exception:
        return "n/a"


def _build_alert_channels(
    payload: Dict[str, Any],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, bool]:
    channels = payload.get("channels")
    if channels is None:
        channels = {}
    if not channels:
        slack_url = payload.get("slack_webhook_url")
        webhook_url = payload.get("webhook_url")
        email_recipients = payload.get("email_recipients")
        if existing:
            if slack_url is None:
                slack_url = existing.get("slack_webhook_url")
            if webhook_url is None:
                webhook_url = existing.get("webhook_url")
            if email_recipients is None:
                email_recipients = existing.get("email_recipients")
        channels = {
            "slack": bool(slack_url),
            "webhook": bool(webhook_url),
            "email": bool(email_recipients),
        }
    return {
        "slack": bool(channels.get("slack")),
        "webhook": bool(channels.get("webhook")),
        "email": bool(channels.get("email")),
    }


def _classify_webhook_exception(exc: Exception) -> str:
    if isinstance(exc, EgressPolicyError):
        return "invalid_url"
    if isinstance(exc, RetryExhaustedError):
        return "timeout"
    msg = str(exc).lower()
    if "timeout" in msg:
        return "timeout"
    if isinstance(exc, ssl.SSLError) or "ssl" in msg or "tls" in msg:
        return "tls"
    if isinstance(exc, socket.gaierror) or "name or service not known" in msg:
        return "dns"
    try:
        import httpx
    except Exception:
        httpx = None  # type: ignore
    if httpx is not None:
        if isinstance(exc, getattr(httpx, "TimeoutException", Exception)):
            return "timeout"
        if isinstance(exc, getattr(httpx, "ConnectError", Exception)):
            if isinstance(getattr(exc, "__cause__", None), ssl.SSLError):
                return "tls"
            if isinstance(getattr(exc, "__cause__", None), socket.gaierror):
                return "dns"
            if "name or service not known" in msg or "dns" in msg:
                return "dns"
    return "other"


def _record_webhook_event(
    *,
    db_path: str,
    user_id: str,
    channel: str,
    status: str,
    attempt: int,
    reason: Optional[str] = None,
    status_code: Optional[int] = None,
    alert_id: Optional[int] = None,
) -> None:
    try:
        db = create_media_database(
            client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
            db_path=db_path,
        )
    except Exception:
        return
    try:
        try:
            db.initialize_db()
        except Exception:
            pass
        payload = {
            "channel": channel,
            "status": status,
            "attempt": int(attempt),
        }
        if reason:
            payload["reason"] = reason
        if status_code is not None:
            payload["status_code"] = int(status_code)
        if alert_id is not None:
            payload["alert_id"] = int(alert_id)
        db.insert_claims_monitoring_event(
            user_id=str(user_id),
            event_type="webhook_delivery",
            severity="info" if status == "success" else "warning",
            payload_json=json.dumps(payload),
        )
    except Exception:
        pass
    finally:
        try:
            db.close_connection()
        except Exception:
            pass


def _deliver_claims_alert_webhook(
    *,
    url: str,
    payload: Dict[str, Any],
    channel: str,
    db_path: str,
    user_id: str,
    alert_id: Optional[int] = None,
) -> None:
    try:
        from tldw_Server_API.app.core.http_client import create_client, fetch, RetryPolicy
    except Exception:
        return
    backoff_schedule = [5, 15, 45, 120, 300]
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            base_delay = backoff_schedule[min(attempt - 2, len(backoff_schedule) - 1)]
            jitter = random.uniform(0.8, 1.2)
            time.sleep(max(0.0, base_delay * jitter))
        start_ts = time.time()
        try:
            with create_client(timeout=5.0) as client:
                response = fetch(
                    method="POST",
                    url=url,
                    client=client,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=5.0,
                    retry=RetryPolicy(attempts=1, retry_on_unsafe=False),
                )
            status_code = int(getattr(response, "status_code", 0) or 0)
            duration = time.time() - start_ts
            if 200 <= status_code < 300:
                logger.info(
                    "Claims webhook delivered channel=%s attempt=%s status=%s",
                    channel,
                    attempt,
                    status_code,
                )
                record_claims_webhook_delivery(status="success", latency_s=duration)
                _record_webhook_event(
                    db_path=db_path,
                    user_id=user_id,
                    channel=channel,
                    status="success",
                    attempt=attempt,
                    status_code=status_code,
                    alert_id=alert_id,
                )
                return
            if 400 <= status_code < 500:
                reason = "http_4xx"
            elif 500 <= status_code < 600:
                reason = "http_5xx"
            else:
                reason = "other"
            logger.warning(
                "Claims webhook failed channel=%s attempt=%s status=%s reason=%s",
                channel,
                attempt,
                status_code,
                reason,
            )
            record_claims_webhook_delivery(status="failure", reason=reason, latency_s=duration)
            _record_webhook_event(
                db_path=db_path,
                user_id=user_id,
                channel=channel,
                status="failure",
                attempt=attempt,
                reason=reason,
                status_code=status_code,
                alert_id=alert_id,
            )
        except Exception as exc:
            reason = _classify_webhook_exception(exc)
            duration = time.time() - start_ts
            logger.warning(
                "Claims webhook failed channel=%s attempt=%s reason=%s",
                channel,
                attempt,
                reason,
            )
            record_claims_webhook_delivery(status="failure", reason=reason, latency_s=duration)
            _record_webhook_event(
                db_path=db_path,
                user_id=user_id,
                channel=channel,
                status="failure",
                attempt=attempt,
                reason=reason,
                alert_id=alert_id,
            )
        if attempt >= max_attempts:
            return

def _claims_monitoring_system_user_id() -> int:
    try:
        return int(settings.get("CLAIMS_MONITORING_SYSTEM_USER_ID", 0))
    except Exception:
        return 0


def _parse_iso_timestamp(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        normalized = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).timestamp()
    except Exception:
        return None


def _format_utc_timestamp(value: Optional[float]) -> Optional[str]:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    except Exception:
        return None


def _build_rebuild_health_summary_from_persisted(persisted: Dict[str, Any]) -> Dict[str, Any]:
    now_ts = datetime.utcnow().timestamp()
    heartbeat_ts = _parse_iso_timestamp(persisted.get("last_worker_heartbeat")) or 0.0
    age_sec = now_ts - heartbeat_ts if heartbeat_ts > 0 else None
    warn_threshold = int(settings.get("CLAIMS_REBUILD_HEARTBEAT_WARN_SEC", 600))
    stale = age_sec is not None and age_sec > warn_threshold
    last_failure = None
    if persisted.get("last_failure_reason") or persisted.get("last_failure_at"):
        last_failure = {
            "error": persisted.get("last_failure_reason"),
            "timestamp": persisted.get("last_failure_at"),
        }
    return {
        "status": "ok",
        "queue_length": int(persisted.get("queue_size") or 0),
        "workers": int(persisted.get("worker_count") or 0),
        "last_heartbeat_ts": heartbeat_ts,
        "heartbeat_age_sec": age_sec,
        "last_processed_ts": _parse_iso_timestamp(persisted.get("last_processed_at")),
        "last_failure": last_failure,
        "stale": stale,
    }


def _build_rebuild_health_summary_from_service(health: Dict[str, Any]) -> Dict[str, Any]:
    now_ts = datetime.utcnow().timestamp()
    heartbeat_ts = float(health.get("last_heartbeat_ts") or 0.0)
    age_sec = now_ts - heartbeat_ts if heartbeat_ts > 0 else None
    warn_threshold = int(settings.get("CLAIMS_REBUILD_HEARTBEAT_WARN_SEC", 600))
    stale = age_sec is not None and age_sec > warn_threshold
    return {
        "status": "ok",
        "queue_length": int(health.get("queue_length") or 0),
        "workers": int(health.get("workers") or 0),
        "last_heartbeat_ts": heartbeat_ts,
        "heartbeat_age_sec": age_sec,
        "last_processed_ts": health.get("last_processed_ts"),
        "last_failure": health.get("last_failure"),
        "stale": stale,
    }


def _load_persisted_rebuild_health() -> Dict[str, Any]:
    user_id = _claims_monitoring_system_user_id()
    db_path = get_user_media_db_path(user_id)
    db = create_media_database(
        client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
        db_path=db_path,
    )
    try:
        try:
            db.initialize_db()
        except Exception:
            pass
        return db.get_claims_monitoring_health(str(user_id))
    finally:
        try:
            db.close_connection()
        except Exception:
            pass


def _dispatch_claims_alert_notifications(
    *,
    config_row: Dict[str, Any],
    payload: Dict[str, Any],
    db_path: str,
    user_id: str,
) -> None:
    """Dispatch best-effort notifications for a claims alert."""
    channels = _normalize_channels(config_row.get("channels_json") or config_row.get("channels"))
    slack_url = config_row.get("slack_webhook_url")
    webhook_url = config_row.get("webhook_url")
    alert_id = config_row.get("id")
    if channels.get("slack") and slack_url:
        slack_payload = {
            "text": (
                "Claims alert: unsupported ratio "
                f"{_format_ratio(payload.get('window_ratio'))} "
                f"(threshold {_format_ratio(payload.get('threshold'))}, "
                f"baseline {_format_ratio(payload.get('baseline_ratio'))})"
            )
        }
        threading.Thread(
            target=_deliver_claims_alert_webhook,
            kwargs={
                "url": str(slack_url),
                "payload": slack_payload,
                "channel": "slack",
                "db_path": db_path,
                "user_id": user_id,
                "alert_id": alert_id,
            },
            daemon=True,
        ).start()
    if channels.get("webhook") and webhook_url:
        threading.Thread(
            target=_deliver_claims_alert_webhook,
            kwargs={
                "url": str(webhook_url),
                "payload": payload,
                "channel": "webhook",
                "db_path": db_path,
                "user_id": user_id,
                "alert_id": alert_id,
            },
            daemon=True,
        ).start()


async def _send_claims_alert_email_digest(
    *,
    recipients: List[str],
    subject: str,
    html_body: str,
    text_body: str,
    email_service: Optional[Any] = None,
) -> bool:
    if not recipients:
        return False
    service = email_service or _get_email_service()
    deliveries: List[bool] = []
    for addr in recipients:
        try:
            ok = await service.send_email(
                to_email=addr,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
            deliveries.append(bool(ok))
        except Exception:
            deliveries.append(False)
    return any(deliveries)


def _format_alert_digest_entry(event: Dict[str, Any], alert_name: str) -> tuple[str, str]:
    payload = event.get("payload") or {}
    created_at = event.get("created_at") or "unknown"
    window_ratio = _format_ratio(payload.get("window_ratio"))
    baseline_ratio = _format_ratio(payload.get("baseline_ratio"))
    threshold = _format_ratio(payload.get("threshold"))
    drift_val = payload.get("drift")
    drift_str = _format_ratio(drift_val) if drift_val is not None else "n/a"
    text = (
        f"- {created_at} | alert={alert_name} | window={window_ratio} | "
        f"baseline={baseline_ratio} | threshold={threshold} | drift={drift_str}"
    )
    html_line = (
        "<li>"
        f"<strong>{html.escape(alert_name)}</strong> "
        f"({html.escape(str(created_at))}) "
        f"window {html.escape(window_ratio)}, baseline {html.escape(baseline_ratio)}, "
        f"threshold {html.escape(threshold)}, drift {html.escape(drift_str)}"
        "</li>"
    )
    return text, html_line


async def send_claims_alert_email_digest_for_scheduler(
    *,
    target_user_id: str,
    db: MediaDatabase,
    interval_sec: Optional[int] = None,
    max_events: Optional[int] = None,
    email_service: Optional[Any] = None,
) -> Dict[str, Any]:
    if not bool(settings.get("CLAIMS_ALERT_EMAIL_DIGEST_ENABLED", False)):
        return {"sent": 0, "events": 0, "skipped": "disabled"}

    try:
        interval_val = int(interval_sec or settings.get("CLAIMS_ALERT_EMAIL_DIGEST_INTERVAL_SEC", 86400))
    except Exception:
        interval_val = 86400
    try:
        limit_val = int(max_events or settings.get("CLAIMS_ALERT_EMAIL_DIGEST_MAX_EVENTS", 500))
    except Exception:
        limit_val = 500
    limit_val = max(1, min(5000, limit_val))

    last_delivered = db.get_latest_claims_monitoring_event_delivery(
        user_id=str(target_user_id),
        event_type="unsupported_ratio",
    )
    if last_delivered:
        last_ts = _parse_iso_timestamp(str(last_delivered))
        if last_ts is not None:
            age_sec = datetime.utcnow().timestamp() - last_ts
            if age_sec < interval_val:
                return {"sent": 0, "events": 0, "skipped": "interval"}

    raw_events = db.list_undelivered_claims_monitoring_events(
        user_id=str(target_user_id),
        event_type="unsupported_ratio",
        limit=limit_val,
    )
    if not raw_events:
        return {"sent": 0, "events": 0, "skipped": "no_events"}

    defaults = db.get_claims_monitoring_settings(str(target_user_id)) or {}
    if defaults and not bool(defaults.get("enabled", True)):
        return {"sent": 0, "events": 0, "skipped": "monitoring_disabled"}

    configs = db.list_claims_monitoring_alerts(str(target_user_id))
    config_by_id = {int(row.get("id")): dict(row) for row in configs if row.get("id") is not None}

    normalized_events = [_normalize_monitoring_event_row(row) for row in raw_events]
    grouped: Dict[Tuple[str, ...], List[Dict[str, Any]]] = {}
    group_alert_names: Dict[Tuple[str, ...], Dict[int, str]] = {}
    undelivered_ids: List[int] = []

    for event in normalized_events:
        payload = event.get("payload") or {}
        alert_id = payload.get("alert_id")
        alert_name = str(payload.get("alert_name") or "Claims alert")
        config_row = None
        try:
            if alert_id is not None:
                config_row = config_by_id.get(int(alert_id))
        except Exception:
            config_row = None

        channels = _normalize_channels(
            (config_row or {}).get("channels_json") or (config_row or {}).get("channels")
        )
        recipients = _parse_email_recipients((config_row or {}).get("email_recipients"))
        if not recipients:
            recipients = _parse_email_recipients(defaults.get("email_recipients"))
        if recipients and not any(channels.values()):
            channels["email"] = True

        if not recipients or not channels.get("email"):
            continue

        key = tuple(sorted(set(str(r) for r in recipients if r)))
        grouped.setdefault(key, []).append(event)
        names = group_alert_names.setdefault(key, {})
        if alert_id is not None:
            try:
                names[int(alert_id)] = config_row.get("name") if config_row else alert_name
            except Exception:
                names[int(alert_id)] = alert_name
        else:
            names[-1] = alert_name

    sent_groups = 0
    for recipients, events in grouped.items():
        if not events:
            continue
        lines: List[str] = []
        html_lines: List[str] = []
        name_map = group_alert_names.get(recipients, {})
        for event in events:
            payload = event.get("payload") or {}
            alert_id = payload.get("alert_id")
            if alert_id is not None and int(alert_id) in name_map:
                alert_name = str(name_map[int(alert_id)])
            else:
                alert_name = str(payload.get("alert_name") or "Claims alert")
            text_line, html_line = _format_alert_digest_entry(event, alert_name)
            lines.append(text_line)
            html_lines.append(html_line)

        subject = f"Claims alert digest ({len(events)} events)"
        text_body = "Claims alert digest:\n" + "\n".join(lines)
        html_body = (
            "<h2>Claims alert digest</h2>"
            f"<p>{len(events)} events.</p>"
            "<ul>"
            + "".join(html_lines)
            + "</ul>"
        )
        start_ts = time.time()
        ok = await _send_claims_alert_email_digest(
            recipients=list(recipients),
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            email_service=email_service,
        )
        duration = time.time() - start_ts
        if ok:
            sent_groups += 1
            for event in events:
                try:
                    undelivered_ids.append(int(event.get("id")))
                except Exception:
                    continue
            record_claims_alert_email_delivery(status="success", latency_s=duration)
        else:
            record_claims_alert_email_delivery(status="failure", latency_s=duration)

    if undelivered_ids:
        db.mark_claims_monitoring_events_delivered(undelivered_ids)

    return {
        "sent": sent_groups,
        "events": len(undelivered_ids),
        "skipped": None if sent_groups else "no_recipients",
    }


def _refresh_claim_embedding(
    *,
    claim_id: int,
    media_id: int,
    chunk_index: int,
    old_text: str,
    new_text: str,
    user_id: str,
) -> None:
    """Best-effort re-embed updated claim text into the claims collection."""
    if not bool(settings.get("CLAIMS_EMBED", False)):
        return
    if not new_text or new_text == old_text:
        return
    try:
        from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import (
            ChromaDBManager,
            create_embeddings_batch,
        )
    except Exception:
        return
    embedding_config = dict(settings.get("EMBEDDING_CONFIG") or {})
    embedding_config["USER_DB_BASE_DIR"] = settings.get("USER_DB_BASE_DIR")
    if not embedding_config.get("USER_DB_BASE_DIR"):
        return
    try:
        manager = ChromaDBManager(user_id=str(user_id), user_embedding_config=embedding_config)
    except Exception:
        return
    collection_name = f"claims_for_{user_id}"
    try:
        collection = manager.get_or_create_collection(collection_name)
    except Exception:
        return

    old_id = claim_embedding_id(media_id, chunk_index, old_text)
    new_id = claim_embedding_id(media_id, chunk_index, new_text)
    try:
        collection.delete(ids=[old_id])
    except Exception:
        try:
            collection.delete(where={"media_id": str(media_id), "claim_text": str(old_text)})
        except Exception:
            pass

    model_id = (
        settings.get("CLAIMS_EMBED_MODEL_ID")
        or embedding_config.get("default_model_id")
        or embedding_config.get("embedding_model")
    )
    try:
        embeddings = create_embeddings_batch(
            texts=[new_text],
            user_app_config=embedding_config,
            model_id_override=model_id,
        )
    except Exception:
        return

    metadata = {
        "source": "claim",
        "media_id": str(media_id),
        "chunk_index": int(chunk_index),
        "claim_text": str(new_text),
        "claim_id": str(claim_id),
    }
    try:
        collection.upsert(
            documents=[new_text],
            embeddings=embeddings,
            ids=[new_id],
            metadatas=[metadata],
        )
    except Exception:
        return


def _claims_settings_snapshot() -> Dict[str, Any]:
    return {
        "enable_ingestion_claims": bool(settings.get("ENABLE_INGESTION_CLAIMS", False)),
        "claim_extractor_mode": str(settings.get("CLAIM_EXTRACTOR_MODE", "heuristic")),
        "claims_max_per_chunk": int(settings.get("CLAIMS_MAX_PER_CHUNK", 3)),
        "claims_embed": bool(settings.get("CLAIMS_EMBED", False)),
        "claims_embed_model_id": str(settings.get("CLAIMS_EMBED_MODEL_ID", "")),
        "claims_cluster_method": str(settings.get("CLAIMS_CLUSTER_METHOD", "embeddings")),
        "claims_cluster_similarity_threshold": float(settings.get("CLAIMS_CLUSTER_SIMILARITY_THRESHOLD", 0.85)),
        "claims_cluster_batch_size": int(settings.get("CLAIMS_CLUSTER_BATCH_SIZE", 200)),
        "claims_llm_provider": str(settings.get("CLAIMS_LLM_PROVIDER", "")),
        "claims_llm_temperature": float(settings.get("CLAIMS_LLM_TEMPERATURE", 0.1)),
        "claims_llm_model": str(settings.get("CLAIMS_LLM_MODEL", "")),
        "claims_rebuild_enabled": bool(settings.get("CLAIMS_REBUILD_ENABLED", False)),
        "claims_rebuild_interval_sec": int(settings.get("CLAIMS_REBUILD_INTERVAL_SEC", 3600)),
        "claims_rebuild_policy": str(settings.get("CLAIMS_REBUILD_POLICY", "missing")),
        "claims_stale_days": int(settings.get("CLAIMS_STALE_DAYS", 7)),
    }


def _claims_monitoring_settings_snapshot() -> Dict[str, Any]:
    return {
        "threshold_ratio": float(settings.get("CLAIMS_ALERT_THRESHOLD_DEFAULT", 0.2)),
        "baseline_ratio": None,
        "slack_webhook_url": None,
        "webhook_url": None,
        "email_recipients": [],
        "enabled": bool(settings.get("CLAIMS_MONITORING_ENABLED", False)),
    }


async def _ensure_claim_edit_access(
    *,
    principal: AuthPrincipal,
    claim_row: Dict[str, Any],
) -> None:
    if principal.is_admin:
        return

    visibility = str(claim_row.get("media_visibility") or "personal").lower()
    owner_user_id = claim_row.get("media_owner_user_id")
    media_client_id = claim_row.get("media_client_id")
    if visibility == "personal":
        try:
            if owner_user_id is not None and int(owner_user_id) == int(principal.user_id):
                return
        except Exception:
            pass
        if media_client_id is not None and str(media_client_id) == str(principal.user_id):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")

    org_id = claim_row.get("media_org_id")
    team_id = claim_row.get("media_team_id")
    db_pool = await get_db_pool()
    repo = AuthnzOrgsTeamsRepo(db_pool=db_pool)

    if visibility == "org":
        if org_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")
        membership = await repo.get_org_member(int(org_id), int(principal.user_id))
        if not _is_membership_active(membership):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")
        role = str(membership.get("role", "member"))
        if _role_at_least(role, "admin"):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")

    if visibility == "team":
        if team_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")
        org_membership = None
        if org_id is not None:
            org_membership = await repo.get_org_member(int(org_id), int(principal.user_id))
        if _is_membership_active(org_membership):
            org_role = str(org_membership.get("role", "member"))
            if _role_at_least(org_role, "admin"):
                return
        team_membership = await repo.get_team_member(int(team_id), int(principal.user_id))
        if _is_membership_active(team_membership):
            team_role = str(team_membership.get("role", "member"))
            if _role_at_least(team_role, "lead"):
                return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")


def _can_review_claim(principal: AuthPrincipal, claim_row: Dict[str, Any]) -> bool:
    if principal.is_admin:
        return True
    reviewer_id = claim_row.get("reviewer_id")
    review_group = claim_row.get("review_group")
    if reviewer_id is not None:
        try:
            if int(reviewer_id) == int(principal.user_id):
                return True
        except Exception:
            pass
    if review_group:
        try:
            return str(review_group) in [str(r) for r in (principal.roles or [])]
        except Exception:
            return False
    return False


def _ensure_claims_admin(principal: AuthPrincipal) -> None:
    if principal.is_admin or CLAIMS_ADMIN in (principal.permissions or []):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


def _ensure_claims_review(principal: AuthPrincipal) -> None:
    if principal.is_admin:
        return
    perms = set(principal.permissions or [])
    if CLAIMS_ADMIN in perms or CLAIMS_REVIEW in perms:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


def _filter_notifications_for_principal(
    principal: AuthPrincipal,
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if principal.is_admin:
        return rows
    allowed_roles = {str(r) for r in (principal.roles or [])}
    allowed_user = str(principal.user_id) if principal.user_id is not None else ""
    filtered: List[Dict[str, Any]] = []
    for row in rows:
        target_user_id = row.get("target_user_id")
        target_group = row.get("target_review_group")
        if target_user_id and str(target_user_id) == allowed_user:
            filtered.append(row)
            continue
        if target_group and str(target_group) in allowed_roles:
            filtered.append(row)
            continue
    return filtered


def _percentile_value(values: List[int], percentile: float) -> Optional[int]:
    if not values:
        return None
    ordered = sorted(values)
    idx = int(math.ceil(percentile * len(ordered))) - 1
    idx = max(0, min(idx, len(ordered) - 1))
    return int(ordered[idx])


def _percentile_float(values: List[float], percentile: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    idx = int(math.ceil(percentile * len(ordered))) - 1
    idx = max(0, min(idx, len(ordered) - 1))
    return float(ordered[idx])


async def _fetch_claims_provider_usage_async(
    owner_user_id: Optional[str],
) -> List[Dict[str, Any]]:
    db_pool = await get_db_pool()
    pg = await is_postgres_backend()
    operations = ["claims_extract", "claims_verify", "claims_ingestion"]
    user_id_val = None
    if owner_user_id:
        try:
            user_id_val = int(owner_user_id)
        except Exception:
            user_id_val = None

    if pg:
        where = ["operation = ANY(?)"]
        params: List[Any] = [operations]
        if user_id_val is not None:
            where.append("user_id = ?")
            params.append(user_id_val)
        where_clause = " AND ".join(where)
        sql = (
            "SELECT provider, model, operation, "
            "COUNT(*) AS requests, "
            "SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) AS errors, "
            "SUM(COALESCE(total_tokens,0)) AS total_tokens, "
            "SUM(COALESCE(total_cost_usd,0)) AS total_cost_usd, "
            "AVG(latency_ms)::float AS latency_avg_ms, "
            "percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)::float AS latency_p95_ms "
            "FROM llm_usage_log "
            f"WHERE {where_clause} "
            "GROUP BY provider, model, operation "
            "ORDER BY total_cost_usd DESC"
        )
        rows = await db_pool.fetch(sql, params)
        return [
            {
                "provider": str(r.get("provider") or ""),
                "model": str(r.get("model") or ""),
                "operation": str(r.get("operation") or ""),
                "requests": int(r.get("requests") or 0),
                "errors": int(r.get("errors") or 0),
                "total_tokens": int(r.get("total_tokens") or 0),
                "total_cost_usd": float(r.get("total_cost_usd") or 0.0),
                "latency_avg_ms": (float(r.get("latency_avg_ms")) if r.get("latency_avg_ms") is not None else None),
                "latency_p95_ms": (float(r.get("latency_p95_ms")) if r.get("latency_p95_ms") is not None else None),
            }
            for r in rows
        ]

    placeholders = ",".join("?" for _ in operations)
    where = [f"operation IN ({placeholders})"]
    params = list(operations)
    if user_id_val is not None:
        where.append("user_id = ?")
        params.append(user_id_val)
    sql = (
        "SELECT provider, model, operation, status, latency_ms, total_tokens, total_cost_usd "
        "FROM llm_usage_log WHERE " + " AND ".join(where)
    )
    rows = await db_pool.fetchall(sql, params)
    grouped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for row in rows:
        provider = str(row["provider"] if isinstance(row, dict) else row[0])
        model = str(row["model"] if isinstance(row, dict) else row[1])
        operation = str(row["operation"] if isinstance(row, dict) else row[2])
        status = row["status"] if isinstance(row, dict) else row[3]
        latency_ms = row["latency_ms"] if isinstance(row, dict) else row[4]
        total_tokens = row["total_tokens"] if isinstance(row, dict) else row[5]
        total_cost_usd = row["total_cost_usd"] if isinstance(row, dict) else row[6]
        key = (provider, model, operation)
        bucket = grouped.setdefault(
            key,
            {
                "provider": provider,
                "model": model,
                "operation": operation,
                "requests": 0,
                "errors": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "latencies": [],
            },
        )
        bucket["requests"] += 1
        if status is not None and int(status) >= 400:
            bucket["errors"] += 1
        if total_tokens is not None:
            bucket["total_tokens"] += int(total_tokens or 0)
        if total_cost_usd is not None:
            bucket["total_cost_usd"] += float(total_cost_usd or 0.0)
        if latency_ms is not None:
            try:
                bucket["latencies"].append(float(latency_ms))
            except Exception:
                pass
    out: List[Dict[str, Any]] = []
    for bucket in grouped.values():
        latencies = bucket.pop("latencies", [])
        latency_avg = None
        latency_p95 = None
        if latencies:
            latency_avg = sum(latencies) / float(len(latencies))
            latency_p95 = _percentile_float(latencies, 0.95)
        bucket["latency_avg_ms"] = latency_avg
        bucket["latency_p95_ms"] = latency_p95
        out.append(bucket)
    out.sort(key=lambda r: float(r.get("total_cost_usd") or 0.0), reverse=True)
    return out


def _fetch_claims_provider_usage(owner_user_id: Optional[str]) -> List[Dict[str, Any]]:
    try:
        return asyncio.run(_fetch_claims_provider_usage_async(owner_user_id))
    except RuntimeError:
        return []
    except Exception:
        return []


def _build_review_latency_stats(db: MediaDatabase) -> Dict[str, Optional[float]]:
    avg_latency_sec = None
    if db.backend_type == BackendType.POSTGRESQL:
        avg_row = db.execute_query(
            "SELECT AVG(EXTRACT(EPOCH FROM (reviewed_at - created_at))) AS avg_sec "
            "FROM claims WHERE reviewed_at IS NOT NULL AND deleted = 0"
        ).fetchone()
    else:
        avg_row = db.execute_query(
            "SELECT AVG((julianday(reviewed_at) - julianday(created_at)) * 86400.0) AS avg_sec "
            "FROM Claims WHERE reviewed_at IS NOT NULL AND deleted = 0"
        ).fetchone()
    if avg_row:
        try:
            avg_latency_sec = float(avg_row[0]) if avg_row[0] is not None else None
        except Exception:
            avg_latency_sec = None

    total_rows = db.execute_query(
        "SELECT COUNT(*) AS count FROM Claims WHERE reviewed_at IS NOT NULL AND deleted = 0"
    ).fetchone()
    total = int(total_rows[0]) if total_rows and total_rows[0] is not None else 0
    p95_latency = None
    if total > 0:
        offset = max(0, int(math.ceil(total * 0.95)) - 1)
        if db.backend_type == BackendType.POSTGRESQL:
            latency_expr = "EXTRACT(EPOCH FROM (reviewed_at - created_at))"
            sql = (
                "SELECT "
                + latency_expr
                + " AS latency FROM claims "
                "WHERE reviewed_at IS NOT NULL AND deleted = 0 "
                f"ORDER BY {latency_expr} LIMIT 1 OFFSET %s"
            )
            row = db.execute_query(sql, (offset,)).fetchone()
        else:
            latency_expr = "(julianday(reviewed_at) - julianday(created_at)) * 86400.0"
            sql = (
                "SELECT "
                + latency_expr
                + " AS latency FROM Claims "
                "WHERE reviewed_at IS NOT NULL AND deleted = 0 "
                f"ORDER BY {latency_expr} LIMIT 1 OFFSET ?"
            )
            row = db.execute_query(sql, (offset,)).fetchone()
        if row:
            try:
                p95_latency = float(row[0]) if row[0] is not None else None
            except Exception:
                p95_latency = None
    return {
        "avg_review_latency_sec": avg_latency_sec,
        "p95_review_latency_sec": p95_latency,
    }


def _build_review_throughput(db: MediaDatabase, window_days: int) -> Dict[str, Any]:
    window_days = max(1, int(window_days))
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=window_days - 1)
    since_dt = datetime.combine(start_date, datetime.min.time())
    if db.backend_type == BackendType.POSTGRESQL:
        sql = (
            "SELECT DATE(created_at) AS day, COUNT(*) AS count "
            "FROM claims_review_log WHERE created_at >= %s "
            "GROUP BY day ORDER BY day"
        )
        rows = db.execute_query(sql, (since_dt,)).fetchall()
    else:
        sql = (
            "SELECT DATE(created_at) AS day, COUNT(*) AS count "
            "FROM claims_review_log WHERE created_at >= ? "
            "GROUP BY day ORDER BY day"
        )
        rows = db.execute_query(sql, (since_dt.strftime("%Y-%m-%d %H:%M:%S"),)).fetchall()

    counts_by_day: Dict[str, int] = {}
    for row in rows:
        day_val = row[0]
        if day_val is None:
            continue
        day_str = str(day_val)
        counts_by_day[day_str] = int(row[1]) if row[1] is not None else 0

    series: List[Dict[str, Any]] = []
    total = 0
    for i in range(window_days):
        day = start_date + timedelta(days=i)
        day_str = day.isoformat()
        count = int(counts_by_day.get(day_str, 0))
        total += count
        series.append({"date": day_str, "count": count})
    return {"window_days": window_days, "total": total, "daily": series}


def _build_review_status_trends(db: MediaDatabase, window_days: int) -> Dict[str, Any]:
    window_days = max(1, int(window_days))
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=window_days - 1)
    since_dt = datetime.combine(start_date, datetime.min.time())

    if db.backend_type == BackendType.POSTGRESQL:
        sql = (
            "SELECT DATE(created_at) AS day, new_status, COUNT(*) AS count "
            "FROM claims_review_log WHERE created_at >= %s "
            "GROUP BY day, new_status ORDER BY day"
        )
        rows = db.execute_query(sql, (since_dt,)).fetchall()
    else:
        sql = (
            "SELECT DATE(created_at) AS day, new_status, COUNT(*) AS count "
            "FROM claims_review_log WHERE created_at >= ? "
            "GROUP BY day, new_status ORDER BY day"
        )
        rows = db.execute_query(sql, (since_dt.strftime("%Y-%m-%d %H:%M:%S"),)).fetchall()

    counts_by_day: Dict[str, Dict[str, int]] = {}
    for row in rows:
        day_val = row.get("day") if hasattr(row, "get") else row[0]
        status_val = row.get("new_status") if hasattr(row, "get") else row[1]
        count_val = row.get("count") if hasattr(row, "get") else row[2]
        if day_val is None:
            continue
        day_str = str(day_val)
        status_key = str(status_val or "unknown")
        try:
            count_int = int(count_val) if count_val is not None else 0
        except Exception:
            count_int = 0
        if day_str not in counts_by_day:
            counts_by_day[day_str] = {}
        counts_by_day[day_str][status_key] = count_int

    series: List[Dict[str, Any]] = []
    for i in range(window_days):
        day = start_date + timedelta(days=i)
        day_str = day.isoformat()
        status_counts = dict(counts_by_day.get(day_str, {}))
        total = sum(status_counts.values())
        series.append({"date": day_str, "total": total, "status_counts": status_counts})
    return {"window_days": window_days, "daily": series}


def _build_claims_per_media_stats(db: MediaDatabase) -> Tuple[List[Dict[str, int]], Dict[str, Optional[float]]]:
    media_rows = db.execute_query(
        "SELECT media_id, COUNT(*) AS count FROM Claims WHERE deleted = 0 GROUP BY media_id"
    ).fetchall()
    media_counts = [{"media_id": int(r[0]), "count": int(r[1])} for r in media_rows if r]
    counts = [row["count"] for row in media_counts]
    mean_val = float(sum(counts) / len(counts)) if counts else None
    p95_val = _percentile_value(counts, 0.95) if counts else None
    max_val = max(counts) if counts else None
    top = sorted(media_counts, key=lambda row: row["count"], reverse=True)[:50]
    return top, {"mean": mean_val, "p95": p95_val, "max": max_val}


def _build_cluster_stats(db: MediaDatabase, owner_user_id: Optional[str]) -> Dict[str, Any]:
    conditions: List[str] = []
    params: List[Any] = []
    if owner_user_id:
        conditions.append("c.user_id = ?")
        params.append(str(owner_user_id))

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = (
        "SELECT c.id, c.canonical_claim_text, c.watchlist_count, c.updated_at, "
        "COALESCE(m.member_count, 0) AS member_count "
        "FROM claim_clusters c "
        "LEFT JOIN (SELECT cluster_id, COUNT(*) AS member_count "
        "FROM claim_cluster_membership GROUP BY cluster_id) m "
        "ON m.cluster_id = c.id "
        f"{where_clause}"
    )
    rows = db.execute_query(sql, tuple(params)).fetchall()
    cluster_rows = [dict(row) for row in rows if row]
    member_counts = [int(row.get("member_count") or 0) for row in cluster_rows]
    total_clusters = len(cluster_rows)
    clusters_with_members = sum(1 for count in member_counts if count > 0)
    total_members = sum(member_counts)
    avg_member_count = (
        float(total_members) / float(clusters_with_members) if clusters_with_members > 0 else None
    )
    p95_member_count = _percentile_value(member_counts, 0.95) if member_counts else None
    max_member_count = max(member_counts) if member_counts else None

    orphan_row = db.execute_query(
        "SELECT COUNT(*) AS count FROM Claims WHERE deleted = 0 AND claim_cluster_id IS NULL"
    ).fetchone()
    orphan_claims = int(orphan_row[0]) if orphan_row and orphan_row[0] is not None else 0

    top_clusters = sorted(cluster_rows, key=lambda row: int(row.get("member_count") or 0), reverse=True)[:20]
    top_payload = []
    for row in top_clusters:
        top_payload.append(
            {
                "cluster_id": int(row.get("id") or 0),
                "member_count": int(row.get("member_count") or 0),
                "watchlist_count": int(row.get("watchlist_count") or 0),
                "canonical_claim_text": row.get("canonical_claim_text"),
                "updated_at": row.get("updated_at"),
            }
        )

    hotspot_conditions: List[str] = ["COALESCE(i.issue_count, 0) > 0"]
    hotspot_params: List[Any] = []
    if owner_user_id:
        hotspot_conditions.append("c.user_id = ?")
        hotspot_params.append(str(owner_user_id))
    hotspot_where = f"WHERE {' AND '.join(hotspot_conditions)}" if hotspot_conditions else ""
    hotspot_sql = (
        "SELECT c.id, c.canonical_claim_text, c.watchlist_count, c.updated_at, "
        "COALESCE(m.member_count, 0) AS member_count, "
        "COALESCE(i.issue_count, 0) AS issue_count "
        "FROM claim_clusters c "
        "LEFT JOIN (SELECT cluster_id, COUNT(*) AS member_count "
        "FROM claim_cluster_membership GROUP BY cluster_id) m "
        "ON m.cluster_id = c.id "
        "LEFT JOIN (SELECT claim_cluster_id AS cluster_id, COUNT(*) AS issue_count "
        "FROM Claims WHERE deleted = 0 AND claim_cluster_id IS NOT NULL "
        "AND review_status IN ('flagged', 'rejected') "
        "GROUP BY claim_cluster_id) i "
        "ON i.cluster_id = c.id "
        f"{hotspot_where} "
        "ORDER BY issue_count DESC, member_count DESC LIMIT 20"
    )
    hotspot_rows = db.execute_query(hotspot_sql, tuple(hotspot_params)).fetchall()
    hotspots: List[Dict[str, Any]] = []
    for row in hotspot_rows:
        member_count = int(row.get("member_count") or 0)
        issue_count = int(row.get("issue_count") or 0)
        issue_ratio = None
        if member_count > 0:
            issue_ratio = issue_count / float(member_count)
        hotspots.append(
            {
                "cluster_id": int(row.get("id") or 0),
                "member_count": member_count,
                "issue_count": issue_count,
                "issue_ratio": issue_ratio,
                "watchlist_count": int(row.get("watchlist_count") or 0),
                "canonical_claim_text": row.get("canonical_claim_text"),
                "updated_at": row.get("updated_at"),
            }
        )

    return {
        "total_clusters": total_clusters,
        "clusters_with_members": clusters_with_members,
        "total_members": total_members,
        "avg_member_count": avg_member_count,
        "p95_member_count": p95_member_count,
        "max_member_count": max_member_count,
        "orphan_claims": orphan_claims,
        "top_clusters": top_payload,
        "hotspots": hotspots,
    }


def _build_claims_analytics(db: MediaDatabase, owner_user_id: Optional[str], window_days: int) -> Dict[str, Any]:
    status_rows = db.execute_query(
        "SELECT review_status, COUNT(*) AS count FROM Claims WHERE deleted = 0 GROUP BY review_status"
    ).fetchall()
    status_counts = {str(r[0]): int(r[1]) for r in status_rows if r and r[0] is not None}
    total_claims = sum(status_counts.values())
    backlog = int(status_counts.get("pending", 0)) + int(status_counts.get("reassigned", 0))

    latency_stats = _build_review_latency_stats(db)
    top_media, media_stats = _build_claims_per_media_stats(db)
    review_throughput = _build_review_throughput(db, window_days)
    review_status_trends = _build_review_status_trends(db, window_days)
    cluster_stats = _build_cluster_stats(db, owner_user_id)

    return {
        "total_claims": total_claims,
        "status_counts": status_counts,
        "avg_review_latency_sec": latency_stats.get("avg_review_latency_sec"),
        "p95_review_latency_sec": latency_stats.get("p95_review_latency_sec"),
        "review_backlog": backlog,
        "claims_per_media_top": top_media,
        "claims_per_media_stats": media_stats,
        "review_throughput": review_throughput,
        "review_status_trends": review_status_trends,
        "clusters": cluster_stats,
    }


def _compute_unsupported_ratios(window_sec: int, baseline_sec: int) -> Dict[str, Optional[float]]:
    try:
        from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
    except Exception:
        return {"window_ratio": None, "baseline_ratio": None}

    reg = get_metrics_registry()
    now = time.time()

    def _sum_since(metric_name: str, since_ts: float) -> float:
        values = reg.values.get(metric_name) or []
        total = 0.0
        for sample in values:
            try:
                if float(sample.timestamp) >= since_ts:
                    total += float(sample.value)
            except Exception:
                continue
        return total

    window_since = now - max(1, int(window_sec))
    baseline_since = now - max(1, int(baseline_sec))

    total_window = _sum_since("rag_total_claims_checked_total", window_since)
    unsupported_window = _sum_since("rag_unsupported_claims_total", window_since)
    total_baseline = _sum_since("rag_total_claims_checked_total", baseline_since)
    unsupported_baseline = _sum_since("rag_unsupported_claims_total", baseline_since)

    window_ratio = unsupported_window / total_window if total_window > 0 else None
    baseline_ratio = unsupported_baseline / total_baseline if total_baseline > 0 else None

    return {"window_ratio": window_ratio, "baseline_ratio": baseline_ratio}


@contextmanager
def _resolve_media_db(
    *,
    db: MediaDatabase,
    current_user: User,
    user_id: Optional[int],
    admin_required: bool,
    owner_filter: bool = False,
) -> Tuple[MediaDatabase, Optional[int]]:
    override_db: Optional[MediaDatabase] = None
    owner_user_id: Optional[int] = None
    try:
        if user_id is not None:
            if not getattr(current_user, "is_admin", False) and admin_required:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
            if db.backend_type == BackendType.POSTGRESQL:
                owner_user_id = int(user_id) if owner_filter else None
                target_db = db
            else:
                db_path = get_user_media_db_path(int(user_id))
                override_db = MediaDatabase(
                    db_path=db_path,
                    client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
                )
                target_db = override_db
        else:
            target_db = db
        yield target_db, owner_user_id
    finally:
        if override_db is not None:
            try:
                override_db.close_connection()
            except Exception:
                pass


def list_all_claims(
    *,
    media_id: Optional[int],
    review_status: Optional[str],
    reviewer_id: Optional[int],
    review_group: Optional[str],
    claim_cluster_id: Optional[int],
    limit: int,
    offset: int,
    include_deleted: bool,
    user_id: Optional[int],
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=True,
    ) as (target_db, owner_filter):
        claims = target_db.list_claims(
            media_id=media_id,
            owner_user_id=owner_filter,
            review_status=review_status,
            reviewer_id=reviewer_id,
            review_group=review_group,
            claim_cluster_id=claim_cluster_id,
            limit=limit,
            offset=offset,
            include_deleted=include_deleted,
        )
        return [_normalize_claim_row(dict(row)) for row in claims]


def search_claims(
    *,
    query: str,
    limit: int,
    offset: int,
    group_by_cluster: bool,
    user_id: Optional[int],
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=True,
    ) as (target_db, owner_filter):
        fetch_limit = max(1, int(limit) + int(offset))
        rows = target_db.search_claims(
            query,
            limit=fetch_limit,
            owner_user_id=owner_filter,
        )
        normalized = [_normalize_search_row(dict(r)) for r in rows]
        total = len(normalized)
        sliced = normalized[offset: offset + limit]
        if not group_by_cluster:
            return {
                "query": query,
                "group_by_cluster": False,
                "total": total,
                "results": sliced,
                "clusters": None,
                "orphaned": None,
            }

        clusters: List[Dict[str, Any]] = []
        orphaned: List[Dict[str, Any]] = []
        cluster_ids: List[int] = []
        for row in sliced:
            cluster_id = row.get("claim_cluster_id")
            if cluster_id is None:
                orphaned.append(row)
                continue
            if int(cluster_id) not in cluster_ids:
                cluster_ids.append(int(cluster_id))
        cluster_map = {
            int(c.get("id")): c
            for c in target_db.get_claim_clusters_by_ids(cluster_ids)
            if c.get("id") is not None
        }
        cluster_hits: Dict[int, Dict[str, Any]] = {}
        for row in sliced:
            cluster_id = row.get("claim_cluster_id")
            if cluster_id is None:
                continue
            cluster_id = int(cluster_id)
            entry = cluster_hits.get(cluster_id)
            if entry is None:
                entry = {
                    "cluster_id": cluster_id,
                    "match_count": 0,
                    "top_claim": row,
                }
                cluster_hits[cluster_id] = entry
            entry["match_count"] += 1
        for cluster_id, entry in cluster_hits.items():
            cluster_row = cluster_map.get(cluster_id, {})
            entry["canonical_claim_text"] = cluster_row.get("canonical_claim_text")
            entry["representative_claim_id"] = cluster_row.get("representative_claim_id")
            entry["watchlist_count"] = cluster_row.get("watchlist_count")
            clusters.append(entry)

        return {
            "query": query,
            "group_by_cluster": True,
            "total": total,
            "results": [],
            "clusters": clusters,
            "orphaned": orphaned,
        }


def list_claim_notifications(
    *,
    kind: Optional[str],
    target_user_id: Optional[str],
    target_review_group: Optional[str],
    resource_type: Optional[str],
    resource_id: Optional[str],
    delivered: Optional[bool],
    limit: int,
    offset: int,
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_review(principal)
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        target_user = str(user_id) if user_id is not None else str(current_user.id)
        if not principal.is_admin and target_user_id is not None and str(target_user_id) != str(principal.user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        rows = target_db.list_claim_notifications(
            user_id=target_user,
            kind=kind,
            target_user_id=str(target_user_id) if target_user_id is not None else None,
            target_review_group=str(target_review_group) if target_review_group else None,
            resource_type=str(resource_type) if resource_type else None,
            resource_id=str(resource_id) if resource_id else None,
            delivered=delivered,
            limit=limit,
            offset=offset,
        )
        filtered = _filter_notifications_for_principal(principal, rows)
        return [_normalize_notification_row(row) for row in filtered]


def mark_claim_notifications_delivered(
    *,
    ids: List[int],
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    if not ids:
        return {"status": "ok", "updated": 0}
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        rows = target_db.get_claim_notifications_by_ids(ids)
        filtered = _filter_notifications_for_principal(principal, rows)
        allowed_ids = [int(row.get("id")) for row in filtered if row.get("id") is not None]
        updated = target_db.mark_claim_notifications_delivered(allowed_ids)
        return {"status": "ok", "updated": int(updated)}


def claim_notifications_digest(
    *,
    kind: Optional[str],
    target_user_id: Optional[str],
    target_review_group: Optional[str],
    resource_type: Optional[str],
    resource_id: Optional[str],
    delivered: Optional[bool],
    limit: int,
    offset: int,
    include_items: bool,
    ack: bool,
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        target_user = str(user_id) if user_id is not None else str(current_user.id)
        rows = target_db.list_claim_notifications(
            user_id=target_user,
            kind=kind,
            target_user_id=str(target_user_id) if target_user_id is not None else None,
            target_review_group=str(target_review_group) if target_review_group else None,
            resource_type=str(resource_type) if resource_type else None,
            resource_id=str(resource_id) if resource_id else None,
            delivered=delivered,
            limit=limit,
            offset=offset,
        )
        filtered = _filter_notifications_for_principal(principal, rows)
        counts_by_kind: Dict[str, int] = {}
        counts_by_target_user: Dict[str, int] = {}
        counts_by_review_group: Dict[str, int] = {}
        normalized = [_normalize_notification_row(row) for row in filtered]
        for row in normalized:
            kind_val = str(row.get("kind") or "unknown")
            counts_by_kind[kind_val] = counts_by_kind.get(kind_val, 0) + 1
            target_user = row.get("target_user_id")
            if target_user:
                key = str(target_user)
                counts_by_target_user[key] = counts_by_target_user.get(key, 0) + 1
            target_group = row.get("target_review_group")
            if target_group:
                key = str(target_group)
                counts_by_review_group[key] = counts_by_review_group.get(key, 0) + 1
        if ack:
            allowed_ids = [int(row.get("id")) for row in normalized if row.get("id") is not None]
            target_db.mark_claim_notifications_delivered(allowed_ids)
        payload: Dict[str, Any] = {
            "total": len(normalized),
            "counts_by_kind": counts_by_kind,
            "counts_by_target_user": counts_by_target_user,
            "counts_by_review_group": counts_by_review_group,
        }
        if include_items:
            payload["notifications"] = normalized
        return payload


def get_claims_settings(principal: AuthPrincipal) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    return _claims_settings_snapshot()


def list_claims_extractors(principal: AuthPrincipal) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    from tldw_Server_API.app.core.Claims_Extraction.extractor_catalog import get_claims_extractor_catalog

    return {
        "extractors": get_claims_extractor_catalog(),
        "default_mode": str(settings.get("CLAIM_EXTRACTOR_MODE", "heuristic")),
        "auto_mode": "auto",
    }


def update_claims_settings(
    *,
    payload: Dict[str, Any],
    principal: AuthPrincipal,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    updates: Dict[str, Any] = {}
    if payload.get("enable_ingestion_claims") is not None:
        updates["ENABLE_INGESTION_CLAIMS"] = bool(payload["enable_ingestion_claims"])
    if payload.get("claim_extractor_mode") is not None:
        updates["CLAIM_EXTRACTOR_MODE"] = str(payload["claim_extractor_mode"]).strip()
    if payload.get("claims_max_per_chunk") is not None:
        updates["CLAIMS_MAX_PER_CHUNK"] = int(payload["claims_max_per_chunk"])
    if payload.get("claims_embed") is not None:
        updates["CLAIMS_EMBED"] = bool(payload["claims_embed"])
    if payload.get("claims_embed_model_id") is not None:
        updates["CLAIMS_EMBED_MODEL_ID"] = str(payload["claims_embed_model_id"])
    if payload.get("claims_cluster_method") is not None:
        updates["CLAIMS_CLUSTER_METHOD"] = str(payload["claims_cluster_method"]).strip()
    if payload.get("claims_cluster_similarity_threshold") is not None:
        updates["CLAIMS_CLUSTER_SIMILARITY_THRESHOLD"] = float(payload["claims_cluster_similarity_threshold"])
    if payload.get("claims_cluster_batch_size") is not None:
        updates["CLAIMS_CLUSTER_BATCH_SIZE"] = int(payload["claims_cluster_batch_size"])
    if payload.get("claims_llm_provider") is not None:
        updates["CLAIMS_LLM_PROVIDER"] = str(payload["claims_llm_provider"])
    if payload.get("claims_llm_temperature") is not None:
        updates["CLAIMS_LLM_TEMPERATURE"] = float(payload["claims_llm_temperature"])
    if payload.get("claims_llm_model") is not None:
        updates["CLAIMS_LLM_MODEL"] = str(payload["claims_llm_model"])
    if payload.get("claims_rebuild_enabled") is not None:
        updates["CLAIMS_REBUILD_ENABLED"] = bool(payload["claims_rebuild_enabled"])
    if payload.get("claims_rebuild_interval_sec") is not None:
        updates["CLAIMS_REBUILD_INTERVAL_SEC"] = int(payload["claims_rebuild_interval_sec"])
    if payload.get("claims_rebuild_policy") is not None:
        updates["CLAIMS_REBUILD_POLICY"] = str(payload["claims_rebuild_policy"])
    if payload.get("claims_stale_days") is not None:
        updates["CLAIMS_STALE_DAYS"] = int(payload["claims_stale_days"])

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided")

    for key, value in updates.items():
        settings[key] = value

    if payload.get("persist"):
        try:
            setup_manager.update_config({"Claims": updates})
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _claims_settings_snapshot()


def _normalize_monitoring_config_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    if normalized.get("threshold_ratio") is None:
        normalized["threshold_ratio"] = float(settings.get("CLAIMS_ALERT_THRESHOLD_DEFAULT", 0.2))
    normalized["email_recipients"] = _parse_email_recipients(row.get("email_recipients"))
    normalized["enabled"] = bool(normalized.get("enabled", True))
    return normalized


def get_claims_monitoring_config(
    *,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    row = db.get_claims_monitoring_settings(target_user_id)
    if not row:
        defaults = _claims_monitoring_settings_snapshot()
        email_json = json.dumps(defaults["email_recipients"]) if defaults.get("email_recipients") else None
        row = db.upsert_claims_monitoring_settings(
            user_id=target_user_id,
            threshold_ratio=defaults.get("threshold_ratio"),
            baseline_ratio=defaults.get("baseline_ratio"),
            slack_webhook_url=defaults.get("slack_webhook_url"),
            webhook_url=defaults.get("webhook_url"),
            email_recipients=email_json,
            enabled=defaults.get("enabled"),
        )
    return _normalize_monitoring_config_row(row)


def update_claims_monitoring_config(
    *,
    payload: Dict[str, Any],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    existing = db.get_claims_monitoring_settings(target_user_id) or {}
    if not existing:
        existing = _claims_monitoring_settings_snapshot()

    threshold_ratio = payload.get("threshold_ratio", existing.get("threshold_ratio"))
    baseline_ratio = payload.get("baseline_ratio", existing.get("baseline_ratio"))
    if threshold_ratio is not None and baseline_ratio is not None:
        if float(baseline_ratio) > float(threshold_ratio):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="baseline_ratio must be <= threshold_ratio",
            )

    email_json = None
    if payload.get("email_recipients") is not None:
        email_json = json.dumps(payload["email_recipients"])

    updated = db.upsert_claims_monitoring_settings(
        user_id=target_user_id,
        threshold_ratio=payload.get("threshold_ratio", existing.get("threshold_ratio")),
        baseline_ratio=payload.get("baseline_ratio", existing.get("baseline_ratio")),
        slack_webhook_url=payload.get("slack_webhook_url", existing.get("slack_webhook_url")),
        webhook_url=payload.get("webhook_url", existing.get("webhook_url")),
        email_recipients=email_json if email_json is not None else existing.get("email_recipients"),
        enabled=payload.get("enabled") if payload.get("enabled") is not None else existing.get("enabled"),
    )
    return _normalize_monitoring_config_row(updated)


def list_claims_alerts(
    *,
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))
    try:
        db.migrate_legacy_claims_monitoring_alerts(target_user_id)
    except Exception:
        pass
    rows = db.list_claims_monitoring_alerts(target_user_id)
    return [_normalize_alert_row(dict(r)) for r in rows]


def create_claims_alert(
    *,
    payload: Dict[str, Any],
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))
    try:
        db.migrate_legacy_claims_monitoring_alerts(target_user_id)
    except Exception:
        pass
    name = payload.get("name")
    alert_type = payload.get("alert_type")
    if not name or not alert_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name and alert_type are required")
    channels = _build_alert_channels(payload)
    if not any(channels.values()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one channel must be enabled")
    threshold_val = payload.get("threshold_ratio")
    baseline_val = payload.get("baseline_ratio")
    if threshold_val is not None and baseline_val is not None:
        if float(baseline_val) > float(threshold_val):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="baseline_ratio must be <= threshold_ratio",
            )
    email_json = None
    if payload.get("email_recipients") is not None:
        email_json = json.dumps(payload["email_recipients"])
    alert = db.create_claims_monitoring_alert(
        user_id=target_user_id,
        name=str(name),
        alert_type=str(alert_type),
        threshold_ratio=payload.get("threshold_ratio"),
        baseline_ratio=payload.get("baseline_ratio"),
        channels_json=json.dumps(channels),
        slack_webhook_url=payload.get("slack_webhook_url"),
        webhook_url=payload.get("webhook_url"),
        email_recipients=email_json,
        enabled=payload.get("enabled") if payload.get("enabled") is not None else True,
    )
    if not alert:
        raise HTTPException(status_code=500, detail="Failed to create alert config")
    return _normalize_alert_row(alert)


def update_claims_alert(
    *,
    config_id: int,
    payload: Dict[str, Any],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    try:
        db.migrate_legacy_claims_monitoring_alerts(str(current_user.id))
    except Exception:
        pass
    existing = db.get_claims_monitoring_alert(int(config_id))
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert config not found")
    if not principal.is_admin and str(existing.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    threshold_val = payload.get("threshold_ratio", existing.get("threshold_ratio"))
    baseline_val = payload.get("baseline_ratio", existing.get("baseline_ratio"))
    if threshold_val is not None and baseline_val is not None:
        if float(baseline_val) > float(threshold_val):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="baseline_ratio must be <= threshold_ratio",
            )
    email_json = None
    if payload.get("email_recipients") is not None:
        email_json = json.dumps(payload["email_recipients"])
    channels_json = None
    if (
        payload.get("channels") is not None
        or payload.get("slack_webhook_url") is not None
        or payload.get("webhook_url") is not None
        or payload.get("email_recipients") is not None
    ):
        channels = _build_alert_channels(payload, existing)
        if not any(channels.values()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one channel must be enabled",
            )
        channels_json = json.dumps(channels)
    updated = db.update_claims_monitoring_alert(
        int(config_id),
        name=payload.get("name"),
        alert_type=payload.get("alert_type"),
        threshold_ratio=payload.get("threshold_ratio"),
        baseline_ratio=payload.get("baseline_ratio"),
        channels_json=channels_json,
        slack_webhook_url=payload.get("slack_webhook_url"),
        webhook_url=payload.get("webhook_url"),
        email_recipients=email_json,
        enabled=payload.get("enabled"),
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update alert config")
    return _normalize_alert_row(updated)


def delete_claims_alert(
    *,
    config_id: int,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    try:
        db.migrate_legacy_claims_monitoring_alerts(str(current_user.id))
    except Exception:
        pass
    existing = db.get_claims_monitoring_alert(int(config_id))
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert config not found")
    if not principal.is_admin and str(existing.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    db.delete_claims_monitoring_alert(int(config_id))
    return {"status": "deleted", "id": int(config_id)}


def evaluate_claims_alerts(
    *,
    window_sec: int,
    baseline_sec: int,
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))
    return _evaluate_claims_alerts_for_user(
        target_user_id=target_user_id,
        db=db,
        window_sec=window_sec,
        baseline_sec=baseline_sec,
    )


def evaluate_claims_alerts_for_scheduler(
    *,
    target_user_id: str,
    window_sec: int,
    baseline_sec: int,
    db: MediaDatabase,
) -> Dict[str, Any]:
    return _evaluate_claims_alerts_for_user(
        target_user_id=target_user_id,
        db=db,
        window_sec=window_sec,
        baseline_sec=baseline_sec,
    )


def _evaluate_claims_alerts_for_user(
    *,
    target_user_id: str,
    window_sec: int,
    baseline_sec: int,
    db: MediaDatabase,
) -> Dict[str, Any]:
    monitoring_enabled = bool(settings.get("CLAIMS_MONITORING_ENABLED", False))
    try:
        db.migrate_legacy_claims_monitoring_alerts(target_user_id)
    except Exception:
        pass
    ratios = _compute_unsupported_ratios(window_sec, baseline_sec)
    configs = db.list_claims_monitoring_alerts(target_user_id)
    config_defaults = db.get_claims_monitoring_settings(target_user_id) or {}
    if config_defaults and not bool(config_defaults.get("enabled", True)):
        monitoring_enabled = False
    results: List[Dict[str, Any]] = []
    for cfg in configs:
        enabled = bool(cfg.get("enabled", True))
        threshold = cfg.get("threshold_ratio")
        if threshold is None:
            threshold = config_defaults.get("threshold_ratio")
        if threshold is None:
            threshold = settings.get("CLAIMS_ALERT_THRESHOLD_DEFAULT", 0.2)
        try:
            threshold_val = float(threshold)
        except Exception:
            threshold_val = 0.2
        drift_threshold_val = None
        drift_threshold = cfg.get("baseline_ratio")
        if drift_threshold is None:
            drift_threshold = config_defaults.get("baseline_ratio")
        if drift_threshold is not None:
            try:
                drift_threshold_val = float(drift_threshold)
            except Exception:
                drift_threshold_val = None
        window_ratio = ratios.get("window_ratio")
        baseline_ratio = ratios.get("baseline_ratio")
        drift = None
        if window_ratio is not None and baseline_ratio is not None:
            drift = window_ratio - baseline_ratio
        triggered = (
            monitoring_enabled
            and enabled
            and window_ratio is not None
            and (
                window_ratio > threshold_val
                or (drift_threshold_val is not None and drift is not None and drift > drift_threshold_val)
            )
        )
        if triggered:
            payload = {
                "alert_id": cfg.get("id"),
                "alert_name": cfg.get("name"),
                "alert_type": cfg.get("alert_type"),
                "window_ratio": window_ratio,
                "baseline_ratio": baseline_ratio,
                "threshold": threshold_val,
                "drift_threshold": drift_threshold_val,
                "drift": drift,
                "user_id": target_user_id,
                "window_sec": window_sec,
                "baseline_sec": baseline_sec,
            }
            db.insert_claims_monitoring_event(
                user_id=str(target_user_id),
                event_type="unsupported_ratio",
                severity="warning",
                payload_json=json.dumps(payload),
            )
            _dispatch_claims_alert_notifications(
                config_row=dict(cfg),
                payload=payload,
                db_path=db.db_path_str,
                user_id=target_user_id,
            )
        results.append(
            {
                "config_id": cfg.get("id"),
                "enabled": enabled,
                "threshold": threshold_val,
                "baseline_ratio": baseline_ratio,
                "drift_threshold": drift_threshold_val,
                "drift": drift,
                "triggered": triggered,
                "window_ratio": window_ratio,
            }
        )
    return {"monitoring_enabled": monitoring_enabled, "ratios": ratios, "results": results}


def claims_rebuild_status(*, rebuild_service: Any = None) -> Dict[str, Any]:
    """Return statistics about the claims rebuild worker."""
    try:
        svc = rebuild_service or get_claims_rebuild_service()
        try:
            stats = svc.get_stats()
        except Exception:
            stats = {}
        try:
            qlen = svc.get_queue_length()
        except Exception:
            qlen = 0
        try:
            workers = svc.get_worker_count()
        except Exception:
            workers = None
        return {"status": "ok", "stats": stats, "queue_length": qlen, "workers": workers}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def claims_rebuild_health(principal: AuthPrincipal, *, summary: bool = False) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    persisted: Dict[str, Any] = {}
    try:
        persisted = _load_persisted_rebuild_health()
    except Exception:
        persisted = {}
    if summary:
        if persisted:
            return _build_rebuild_health_summary_from_persisted(persisted)
        svc = get_claims_rebuild_service()
        health = svc.get_health()
        return _build_rebuild_health_summary_from_service(health)

    if persisted:
        payload = _build_rebuild_health_summary_from_persisted(persisted)
        payload["last_worker_heartbeat"] = persisted.get("last_worker_heartbeat")
        payload["last_processed_at"] = persisted.get("last_processed_at")
        payload["last_failure_at"] = persisted.get("last_failure_at")
        payload["updated_at"] = persisted.get("updated_at")
        return payload

    svc = get_claims_rebuild_service()
    health = svc.get_health()
    last_failure = health.get("last_failure") or {}
    payload = _build_rebuild_health_summary_from_service(health)
    payload["last_worker_heartbeat"] = _format_utc_timestamp(health.get("last_heartbeat_ts"))
    payload["last_processed_at"] = _format_utc_timestamp(health.get("last_processed_ts"))
    payload["last_failure_at"] = _format_utc_timestamp(last_failure.get("timestamp"))
    payload["updated_at"] = _format_utc_timestamp(time.time())
    return payload


def get_review_queue(
    *,
    status_filter: Optional[str],
    reviewer_id: Optional[int],
    review_group: Optional[str],
    media_id: Optional[int],
    extractor: Optional[str],
    limit: int,
    offset: int,
    include_deleted: bool,
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_review(principal)
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=not principal.is_admin,
        owner_filter=True,
    ) as (target_db, owner_filter):
        if status_filter is None:
            status_filter = "pending"
        if not principal.is_admin:
            if reviewer_id is not None and int(reviewer_id) != int(principal.user_id or 0):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
            if review_group is not None:
                if str(review_group) not in [str(r) for r in (principal.roles or [])]:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
            if reviewer_id is None and review_group is None:
                reviewer_id = int(principal.user_id or 0)

        rows = target_db.list_review_queue(
            status=status_filter,
            reviewer_id=reviewer_id,
            review_group=review_group,
            media_id=media_id,
            extractor=extractor,
            owner_user_id=owner_filter,
            limit=limit,
            offset=offset,
            include_deleted=include_deleted,
        )
        record_claims_review_metrics(queue_size=len(rows))
        return [_normalize_claim_row(dict(r)) for r in rows]


async def review_claim(
    *,
    claim_id: int,
    payload: Dict[str, Any],
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
    request: Any = None,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=not principal.is_admin,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        claim_row = target_db.get_claim_with_media(int(claim_id), include_deleted=True)
        if not claim_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

        current_status = str(claim_row.get("review_status") or "pending").lower()
        new_status = str(payload.get("status")).lower()
        if not _is_review_transition_allowed(current_status, new_status):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid review transition")
        if new_status == "reassigned" and not (payload.get("reviewer_id") or payload.get("review_group")):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reassigned requires reviewer or group")

        reviewer_id = payload.get("reviewer_id")
        if not principal.is_admin:
            if reviewer_id is not None and int(reviewer_id) != int(principal.user_id or 0):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
            reviewer_id = int(principal.user_id or 0)
            if payload.get("review_group") is not None:
                if str(payload.get("review_group")) not in [str(r) for r in (principal.roles or [])]:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        if not principal.is_admin and not _can_review_claim(principal, claim_row):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        action_ip, action_user_agent = _extract_request_metadata(request)

        corrected_text = payload.get("corrected_text")
        if corrected_text is not None:
            corrected_text = str(corrected_text)
            if not corrected_text.strip():
                corrected_text = None

        span_start = None
        span_end = None
        if corrected_text is not None:
            span_start, span_end = _resolve_corrected_claim_span(
                target_db=target_db,
                claim_row=dict(claim_row),
                corrected_text=corrected_text,
            )

        updated = target_db.update_claim_review(
            int(claim_id),
            review_status=new_status,
            reviewer_id=reviewer_id,
            review_group=payload.get("review_group"),
            review_notes=payload.get("notes"),
            review_reason_code=payload.get("reason_code"),
            corrected_text=corrected_text,
            span_start=span_start,
            span_end=span_end,
            expected_version=int(payload.get("review_version")),
            action_ip=action_ip,
            action_user_agent=action_user_agent,
        )
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
        if isinstance(updated, dict) and updated.get("conflict"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "version_conflict",
                    "current": updated.get("current"),
                },
            )
        latency_s = None
        try:
            created_at_raw = claim_row.get("created_at")
            if created_at_raw:
                created_at = datetime.fromisoformat(str(created_at_raw).replace("Z", "+00:00"))
                latency_s = (datetime.utcnow().replace(tzinfo=created_at.tzinfo) - created_at).total_seconds()
        except Exception:
            latency_s = None
        record_claims_review_metrics(processed=1, latency_s=latency_s)
        if new_status in {"flagged", "reassigned"} and new_status != current_status:
            _enqueue_claim_rebuild_if_needed(
                media_id=int(claim_row.get("media_id") or 0),
                db_path=str(target_db.db_path_str),
            )
        if corrected_text is not None:
            target_user_id = str(user_id) if user_id is not None else str(current_user.id)
            _refresh_claim_embedding(
                claim_id=int(claim_id),
                media_id=int(claim_row.get("media_id") or 0),
                chunk_index=int(claim_row.get("chunk_index") or 0),
                old_text=str(claim_row.get("claim_text") or ""),
                new_text=str(corrected_text),
                user_id=target_user_id,
            )
        owner_user_id = _resolve_claim_owner_user_id(
            claim_row,
            int(user_id) if user_id is not None else int(current_user.id),
        )
        if owner_user_id:
            try:
                notif_payload = {
                    "claim_id": int(claim_id),
                    "claim_uuid": claim_row.get("uuid"),
                    "media_id": claim_row.get("media_id"),
                    "chunk_index": claim_row.get("chunk_index"),
                    "claim_text": updated.get("claim_text") if isinstance(updated, dict) else claim_row.get("claim_text"),
                    "old_status": current_status,
                    "new_status": new_status,
                    "reviewer_id": reviewer_id,
                    "review_group": payload.get("review_group"),
                    "notes": payload.get("notes"),
                    "reason_code": payload.get("reason_code"),
                    "reviewed_at": updated.get("reviewed_at") if isinstance(updated, dict) else None,
                }
                created = target_db.insert_claim_notification(
                    user_id=str(owner_user_id),
                    kind="review_update",
                    target_user_id=str(reviewer_id) if reviewer_id is not None else None,
                    target_review_group=str(payload.get("review_group")) if payload.get("review_group") else None,
                    resource_type="claim",
                    resource_id=str(claim_id),
                    payload_json=json.dumps(notif_payload),
                )
                notif_id = created.get("id") if isinstance(created, dict) else None
                if notif_id is not None:
                    dispatch_claim_review_notifications(
                        db_path=str(target_db.db_path_str),
                        owner_user_id=str(owner_user_id),
                        notification_ids=[int(notif_id)],
                    )
            except Exception as exc:
                logger.debug("Failed to emit claims review notification: %s", exc)
        return _normalize_claim_row(dict(updated))


def get_claim_review_history(
    *,
    claim_id: int,
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_review(principal)
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=not principal.is_admin,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        claim_row = target_db.get_claim_with_media(int(claim_id), include_deleted=True)
        if not claim_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
        if not principal.is_admin and not _can_review_claim(principal, claim_row):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        return target_db.list_claim_review_history(int(claim_id))


def bulk_review_claims(
    *,
    payload: Dict[str, Any],
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
    request: Any = None,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    if str(payload.get("status")).lower() == "reassigned" and not (
        payload.get("reviewer_id") or payload.get("review_group")
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reassigned requires reviewer or group")
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=not principal.is_admin,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        updated_ids: List[int] = []
        conflicts: List[int] = []
        missing: List[int] = []
        invalid: List[int] = []
        rebuild_media_ids: set[int] = set()
        action_ip, action_user_agent = _extract_request_metadata(request)
        desired_status = str(payload.get("status")).lower()
        for cid in payload.get("claim_ids") or []:
            claim_row = target_db.get_claim_with_media(int(cid), include_deleted=True)
            if not claim_row:
                missing.append(int(cid))
                continue
            current_status = str(claim_row.get("review_status") or "pending").lower()
            if not _is_review_transition_allowed(current_status, desired_status):
                invalid.append(int(cid))
                continue
            updated = target_db.update_claim_review(
                int(cid),
                review_status=desired_status,
                reviewer_id=payload.get("reviewer_id"),
                review_group=payload.get("review_group"),
                review_notes=payload.get("notes"),
                review_reason_code=payload.get("reason_code"),
                expected_version=int(claim_row.get("review_version") or 1),
                action_ip=action_ip,
                action_user_agent=action_user_agent,
            )
            if isinstance(updated, dict) and updated.get("conflict"):
                conflicts.append(int(cid))
            elif updated is None:
                missing.append(int(cid))
            else:
                updated_ids.append(int(cid))
                if desired_status in {"flagged", "reassigned"} and desired_status != current_status:
                    try:
                        rebuild_media_ids.add(int(claim_row.get("media_id") or 0))
                    except Exception:
                        pass

        if updated_ids:
            record_claims_review_metrics(processed=len(updated_ids))
        if rebuild_media_ids:
            for media_id in rebuild_media_ids:
                if media_id > 0:
                    _enqueue_claim_rebuild_if_needed(
                        media_id=media_id,
                        db_path=str(target_db.db_path_str),
                    )
        if updated_ids:
            owner_user_id = str(user_id) if user_id is not None else str(current_user.id)
            try:
                notif_payload = {
                    "claim_ids": updated_ids,
                    "status": desired_status,
                    "reviewer_id": payload.get("reviewer_id"),
                    "review_group": payload.get("review_group"),
                    "notes": payload.get("notes"),
                    "reason_code": payload.get("reason_code"),
                }
                created = target_db.insert_claim_notification(
                    user_id=str(owner_user_id),
                    kind="review_bulk_update",
                    target_user_id=str(payload.get("reviewer_id")) if payload.get("reviewer_id") is not None else None,
                    target_review_group=str(payload.get("review_group")) if payload.get("review_group") else None,
                    resource_type="claim",
                    resource_id="bulk",
                    payload_json=json.dumps(notif_payload),
                )
                notif_id = created.get("id") if isinstance(created, dict) else None
                if notif_id is not None:
                    dispatch_claim_review_notifications(
                        db_path=str(target_db.db_path_str),
                        owner_user_id=str(owner_user_id),
                        notification_ids=[int(notif_id)],
                    )
            except Exception as exc:
                logger.debug("Failed to emit claims bulk review notification: %s", exc)
        return {
            "updated": updated_ids,
            "conflicts": conflicts,
            "missing": missing,
            "invalid": invalid,
        }


def list_review_rules(
    *,
    user_id: Optional[int],
    active_only: bool,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))
    rows = db.list_claim_review_rules(target_user_id, active_only=active_only)
    return [_normalize_review_rule(r) for r in rows]


def create_review_rule(
    *,
    payload: Dict[str, Any],
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))
    rule = db.create_claim_review_rule(
        user_id=target_user_id,
        priority=payload.get("priority"),
        predicate_json=json.dumps(payload.get("predicate_json")),
        reviewer_id=payload.get("reviewer_id"),
        review_group=payload.get("review_group"),
        active=payload.get("active") if payload.get("active") is not None else True,
    )
    if not rule:
        raise HTTPException(status_code=500, detail="Failed to create rule")
    return _normalize_review_rule(rule)


def update_review_rule(
    *,
    rule_id: int,
    payload: Dict[str, Any],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    existing = db.get_claim_review_rule(int(rule_id))
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    if not principal.is_admin and str(existing.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    updated = db.update_claim_review_rule(
        int(rule_id),
        priority=payload.get("priority"),
        predicate_json=json.dumps(payload.get("predicate_json")) if payload.get("predicate_json") is not None else None,
        reviewer_id=payload.get("reviewer_id"),
        review_group=payload.get("review_group"),
        active=payload.get("active"),
    )
    return _normalize_review_rule(updated)


def delete_review_rule(
    *,
    rule_id: int,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    existing = db.get_claim_review_rule(int(rule_id))
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    if not principal.is_admin and str(existing.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    db.delete_claim_review_rule(int(rule_id))
    return {"status": "deleted", "id": int(rule_id)}


def review_analytics(principal: AuthPrincipal, db: MediaDatabase) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    owner_user_id = str(principal.user_id) if principal.user_id is not None else None
    return _build_claims_analytics(db, owner_user_id, window_days=7)


def claims_dashboard_analytics(
    *,
    window_days: int,
    window_sec: int,
    baseline_sec: int,
    principal: AuthPrincipal,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    owner_user_id = str(principal.user_id) if principal.user_id is not None else None
    payload = _build_claims_analytics(db, owner_user_id, window_days=window_days)
    ratios = _compute_unsupported_ratios(window_sec, baseline_sec)
    payload["unsupported_ratios"] = {
        "window_sec": int(window_sec),
        "baseline_sec": int(baseline_sec),
        "window_ratio": ratios.get("window_ratio"),
        "baseline_ratio": ratios.get("baseline_ratio"),
    }
    try:
        payload["rebuild_health"] = claims_rebuild_health(principal, summary=True)
    except Exception:
        payload["rebuild_health"] = None
    try:
        metrics_user_id = owner_user_id or str(settings.get("SINGLE_USER_FIXED_ID", "1"))
        today = datetime.utcnow().date()
        start_date = (today - timedelta(days=max(1, int(window_days)) - 1)).isoformat()
        end_date = today.isoformat()
        metrics_rows = db.list_claims_review_extractor_metrics_daily(
            user_id=metrics_user_id,
            start_date=start_date,
            end_date=end_date,
        )
        payload["review_extractor_metrics"] = [
            _normalize_review_extractor_metrics_row(row) for row in metrics_rows
        ]
    except Exception:
        payload["review_extractor_metrics"] = []
    try:
        payload["provider_usage"] = _fetch_claims_provider_usage(owner_user_id)
    except Exception:
        payload["provider_usage"] = []
    return payload


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except Exception:
        return None


def aggregate_claims_review_extractor_metrics_daily(
    *,
    db: MediaDatabase,
    target_user_id: Optional[str] = None,
    report_date: Optional[str] = None,
    lookback_days: Optional[int] = None,
) -> int:
    if db.backend_type == BackendType.POSTGRESQL and not target_user_id:
        logger.debug("Claims review metrics aggregation skipped: missing target_user_id for Postgres")
        return 0

    user_id_value = str(target_user_id or settings.get("SINGLE_USER_FIXED_ID", "1"))
    start_date = _parse_iso_date(report_date)
    if start_date is None:
        try:
            lookback_val = int(
                lookback_days if lookback_days is not None else settings.get("CLAIMS_REVIEW_METRICS_LOOKBACK_DAYS", 2)
            )
        except Exception:
            lookback_val = 2
        lookback_val = max(1, lookback_val)
        today = datetime.utcnow().date()
        start_date = today - timedelta(days=lookback_val - 1)
        end_date = today
    else:
        end_date = start_date

    if start_date is None:
        return 0

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    if db.backend_type == BackendType.POSTGRESQL:
        placeholder = "%s"
        start_param = start_dt
        end_param = end_dt
        claims_table = "claims"
        media_table = "media"
    else:
        placeholder = "?"
        start_param = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_param = end_dt.strftime("%Y-%m-%d %H:%M:%S")
        claims_table = "Claims"
        media_table = "Media"

    owner_filter_sql = ""
    params: List[Any] = [start_param, end_param]
    if db.backend_type == BackendType.POSTGRESQL and target_user_id:
        owner_filter_sql = (
            f" AND COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = {placeholder}"
        )
        params.append(str(target_user_id))

    date_expr = "DATE(l.created_at)"
    metrics_sql = (
        "SELECT "
        + date_expr
        + " AS day, "
        "COALESCE(c.extractor, 'unknown') AS extractor, "
        "COALESCE(c.extractor_version, '') AS extractor_version, "
        "COUNT(*) AS total_reviewed, "
        "SUM(CASE WHEN lower(l.new_status) = 'approved' THEN 1 ELSE 0 END) AS approved_count, "
        "SUM(CASE WHEN lower(l.new_status) = 'rejected' THEN 1 ELSE 0 END) AS rejected_count, "
        "SUM(CASE WHEN lower(l.new_status) = 'flagged' THEN 1 ELSE 0 END) AS flagged_count, "
        "SUM(CASE WHEN lower(l.new_status) = 'reassigned' THEN 1 ELSE 0 END) AS reassigned_count, "
        "SUM(CASE WHEN l.old_text IS NOT NULL AND l.new_text IS NOT NULL AND l.old_text <> l.new_text "
        "THEN 1 ELSE 0 END) AS edited_count "
        "FROM claims_review_log l "
        f"LEFT JOIN {claims_table} c ON c.id = l.claim_id "
        f"LEFT JOIN {media_table} m ON m.id = c.media_id "
        f"WHERE l.created_at >= {placeholder} AND l.created_at < {placeholder}"
        + owner_filter_sql
        + " GROUP BY day, extractor, extractor_version ORDER BY day ASC"
    )

    reason_sql = (
        "SELECT "
        + date_expr
        + " AS day, "
        "COALESCE(c.extractor, 'unknown') AS extractor, "
        "COALESCE(c.extractor_version, '') AS extractor_version, "
        "l.reason_code, COUNT(*) AS count "
        "FROM claims_review_log l "
        f"LEFT JOIN {claims_table} c ON c.id = l.claim_id "
        f"LEFT JOIN {media_table} m ON m.id = c.media_id "
        f"WHERE l.created_at >= {placeholder} AND l.created_at < {placeholder}"
        + owner_filter_sql
        + " GROUP BY day, extractor, extractor_version, l.reason_code"
    )

    metrics_rows = db.execute_query(metrics_sql, tuple(params)).fetchall()
    if not metrics_rows:
        return 0

    reason_rows = db.execute_query(reason_sql, tuple(params)).fetchall()
    reason_counts: Dict[Tuple[str, str, str], Dict[str, int]] = {}
    for row in reason_rows:
        try:
            day_val = row[0]
            extractor_val = row[1]
            version_val = row[2]
            reason_val = row[3]
            count_val = row[4]
        except Exception:
            continue
        if reason_val is None:
            continue
        reason_key = str(reason_val).strip()
        if not reason_key:
            continue
        day_str = day_val.isoformat() if hasattr(day_val, "isoformat") else str(day_val)
        extractor_key = str(extractor_val or "unknown")
        version_key = str(version_val or "")
        key = (day_str, extractor_key, version_key)
        counts_for_key = reason_counts.setdefault(key, {})
        counts_for_key[reason_key] = counts_for_key.get(reason_key, 0) + int(count_val or 0)

    written = 0
    for row in metrics_rows:
        try:
            day_val = row[0]
            extractor_val = row[1]
            version_val = row[2]
            total_reviewed = row[3]
            approved_count = row[4]
            rejected_count = row[5]
            flagged_count = row[6]
            reassigned_count = row[7]
            edited_count = row[8]
        except Exception:
            continue
        day_str = day_val.isoformat() if hasattr(day_val, "isoformat") else str(day_val)
        extractor_key = str(extractor_val or "unknown")
        version_key = str(version_val or "")
        reason_payload = reason_counts.get((day_str, extractor_key, version_key))
        db.upsert_claims_review_extractor_metrics_daily(
            user_id=user_id_value,
            report_date=day_str,
            extractor=extractor_key,
            extractor_version=version_key,
            total_reviewed=int(total_reviewed or 0),
            approved_count=int(approved_count or 0),
            rejected_count=int(rejected_count or 0),
            flagged_count=int(flagged_count or 0),
            reassigned_count=int(reassigned_count or 0),
            edited_count=int(edited_count or 0),
            reason_code_counts_json=json.dumps(reason_payload) if reason_payload else None,
        )
        written += 1

    return written


def list_claims_review_metrics(
    *,
    start_date: Optional[str],
    end_date: Optional[str],
    extractor: Optional[str],
    extractor_version: Optional[str],
    user_id: Optional[int],
    limit: int,
    offset: int,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    target_user_id = str(getattr(current_user, "id", None) or settings.get("SINGLE_USER_FIXED_ID", "1"))
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))

    resolve_user_id = int(user_id) if user_id is not None else None
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=resolve_user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _):
        rows = target_db.list_claims_review_extractor_metrics_daily(
            user_id=target_user_id,
            start_date=start_date,
            end_date=end_date,
            extractor=extractor,
            extractor_version=extractor_version,
            limit=limit,
            offset=offset,
        )
    normalized = [_normalize_review_extractor_metrics_row(row) for row in rows]
    return {"items": normalized, "total": len(normalized)}


def export_claims_analytics(
    *,
    payload: Dict[str, Any],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Any:
    _ensure_claims_admin(principal)
    fmt = str(payload.get("format") or "json").lower()
    if fmt not in {"json", "csv"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported export format")

    filters = payload.get("filters") or {}
    pagination = payload.get("pagination") or {}
    target_user_id = str(current_user.id)
    workspace_id = filters.get("workspace_id")
    if workspace_id:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(workspace_id)

    retention_hours = settings.get("CLAIMS_ANALYTICS_EXPORT_RETENTION_HOURS", 24)
    try:
        retention_val = float(retention_hours)
    except (TypeError, ValueError):
        retention_val = 24.0
    if retention_val > 0:
        try:
            db.cleanup_claims_analytics_exports(user_id=target_user_id, retention_hours=retention_val)
        except Exception as exc:
            logger.debug("Claims analytics export cleanup failed: %s", exc)

    events = db.list_claims_monitoring_events(
        user_id=target_user_id,
        event_type=filters.get("event_type"),
        severity=filters.get("severity"),
        start_time=filters.get("start_time"),
        end_time=filters.get("end_time"),
    )
    normalized_events = [_normalize_monitoring_event_row(row) for row in events]
    filtered_events = _filter_monitoring_events_by_payload(
        normalized_events,
        provider=filters.get("provider"),
        model=filters.get("model"),
    )
    total = len(filtered_events)
    try:
        limit = int(pagination.get("limit", 1000))
    except Exception:
        limit = 1000
    try:
        offset = int(pagination.get("offset", 0))
    except Exception:
        offset = 0
    limit = max(1, min(10000, limit))
    offset = max(0, offset)
    page_events = filtered_events[offset: offset + limit]
    pagination_meta = {
        "limit": limit,
        "offset": offset,
        "total": total,
    }

    export_id = uuid4().hex
    filters_json = json.dumps(filters) if filters else None
    pagination_json = json.dumps(pagination_meta)

    payload_json = None
    payload_csv = None
    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "event_type", "severity", "created_at", "payload_json"])
        for event in page_events:
            writer.writerow(
                [
                    event.get("id"),
                    event.get("event_type"),
                    event.get("severity"),
                    event.get("created_at"),
                    json.dumps(event.get("payload") or {}),
                ]
            )
        payload_csv = output.getvalue()
    else:
        export_payload = {
            "events": page_events,
            "filters": filters,
            "pagination": pagination_meta,
        }
        payload_json = json.dumps(export_payload)

    export_row = db.create_claims_analytics_export(
        export_id=export_id,
        user_id=target_user_id,
        format=fmt,
        status="ready",
        payload_json=payload_json,
        payload_csv=payload_csv,
        filters_json=filters_json,
        pagination_json=pagination_json,
    )

    return {
        "export_id": export_id,
        "format": fmt,
        "status": export_row.get("status", "ready") if export_row else "ready",
        "download_url": f"/api/v1/claims/analytics/export/{export_id}",
        "created_at": export_row.get("created_at") if export_row else None,
    }


def list_claims_analytics_exports(
    *,
    limit: int,
    offset: int,
    status_filter: Optional[str],
    format_filter: Optional[str],
    workspace_id: Optional[str],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    if workspace_id:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(workspace_id)

    if format_filter:
        normalized = str(format_filter).lower()
        if normalized not in {"json", "csv"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported export format")
        format_filter = normalized

    rows = db.list_claims_analytics_exports(
        user_id=target_user_id,
        status=status_filter,
        format=format_filter,
        limit=limit,
        offset=offset,
    )
    total = db.count_claims_analytics_exports(
        user_id=target_user_id,
        status=status_filter,
        format=format_filter,
    )
    exports: List[Dict[str, Any]] = []
    for row in rows:
        filters = None
        pagination = None
        raw_filters = row.get("filters_json")
        if raw_filters:
            try:
                filters = json.loads(raw_filters)
            except Exception:
                filters = None
        raw_pagination = row.get("pagination_json")
        if raw_pagination:
            try:
                pagination = json.loads(raw_pagination)
            except Exception:
                pagination = None
        exports.append(
            {
                "export_id": row.get("export_id"),
                "format": row.get("format"),
                "status": row.get("status"),
                "download_url": f"/api/v1/claims/analytics/export/{row.get('export_id')}",
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "filters": filters,
                "pagination": pagination,
                "error_message": row.get("error_message"),
            }
        )

    return {
        "exports": exports,
        "total": int(total),
        "limit": int(limit),
        "offset": int(offset),
    }


def get_claims_analytics_export(
    *,
    export_id: str,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    row = db.get_claims_analytics_export(str(export_id))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    if not principal.is_admin and str(row.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    fmt = row.get("format")
    if fmt == "csv":
        payload = row.get("payload_csv") or ""
    else:
        raw = row.get("payload_json") or "{}"
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {}
    return {
        "export_id": row.get("export_id"),
        "format": fmt,
        "status": row.get("status"),
        "payload": payload,
    }


def list_claim_clusters(
    *,
    limit: int,
    offset: int,
    updated_since: Optional[str],
    keyword: Optional[str],
    min_size: Optional[int],
    watchlisted: Optional[bool],
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_review(principal)
    target_user_id = str(current_user.id)
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))
    clusters = db.list_claim_clusters(
        target_user_id,
        limit=limit,
        offset=offset,
        updated_since=updated_since,
        keyword=keyword,
        min_size=min_size,
        watchlisted=None,
    )
    counts = _load_watchlist_cluster_counts(target_user_id, [int(c.get("id")) for c in clusters if c.get("id")])
    if counts:
        for cluster in clusters:
            try:
                cluster_id = int(cluster.get("id"))
            except Exception:
                continue
            cluster["watchlist_count"] = int(counts.get(cluster_id, 0))
    if watchlisted is not None:
        clusters = [
            c for c in clusters if (int(c.get("watchlist_count") or 0) > 0) == bool(watchlisted)
        ]
    return clusters


def rebuild_claim_clusters(
    *,
    min_size: int,
    user_id: Optional[int],
    method: Optional[str],
    similarity_threshold: Optional[float],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_admin(principal)
    target_user_id = str(current_user.id)
    if user_id is not None:
        if not principal.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_user_id = str(int(user_id))
    cluster_method = (method or settings.get("CLAIMS_CLUSTER_METHOD", "embeddings") or "embeddings").strip().lower()
    if cluster_method not in {"embeddings", "exact"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid clustering method")

    if user_id is not None and db.backend_type != BackendType.POSTGRESQL:
        db_path = get_user_media_db_path(int(user_id))
        override_db = MediaDatabase(
            db_path=db_path,
            client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
        )
        try:
            if cluster_method == "exact":
                return override_db.rebuild_claim_clusters_exact(user_id=target_user_id, min_size=min_size)
            return rebuild_claim_clusters_embeddings(
                db=override_db,
                user_id=target_user_id,
                min_size=min_size,
                similarity_threshold=similarity_threshold,
            )
        finally:
            try:
                override_db.close_connection()
            except Exception:
                pass

    if cluster_method == "exact":
        result = db.rebuild_claim_clusters_exact(user_id=target_user_id, min_size=min_size)
    else:
        result = rebuild_claim_clusters_embeddings(
            db=db,
            user_id=target_user_id,
            min_size=min_size,
            similarity_threshold=similarity_threshold,
        )

    try:
        watchlist_result = _evaluate_watchlist_cluster_notifications(db, target_user_id)
        result["watchlist_notifications"] = watchlist_result
    except Exception:
        pass
    return result


def _evaluate_watchlist_cluster_notifications(db: MediaDatabase, user_id: str) -> Dict[str, Any]:
    watch_db = _get_watchlists_db(user_id)
    if not watch_db:
        return {"status": "skipped", "reason": "watchlists_unavailable"}
    rows = watch_db.list_watchlist_cluster_subscriptions()
    if not rows:
        return {"status": "skipped", "reason": "no_subscriptions"}
    subscriptions: Dict[int, List[int]] = {}
    for row in rows:
        try:
            cluster_id = int(row.get("cluster_id"))
            job_id = int(row.get("job_id"))
        except Exception:
            continue
        subscriptions.setdefault(cluster_id, []).append(job_id)
    cluster_ids = list(subscriptions.keys())
    clusters = db.get_claim_clusters_by_ids(cluster_ids)
    cluster_map = {int(c.get("id")): c for c in clusters if c.get("id") is not None}
    member_counts = db.get_claim_cluster_member_counts(cluster_ids)
    counts = watch_db.list_watchlist_cluster_counts(cluster_ids=cluster_ids)
    if counts:
        try:
            db.update_claim_clusters_watchlist_counts(counts)
        except Exception:
            pass
    inserted = record_watchlist_cluster_notifications(
        db=db,
        owner_user_id=str(user_id),
        clusters=cluster_map,
        member_counts=member_counts,
        subscriptions=subscriptions,
    )
    return {
        "status": "ok",
        "subscriptions": len(subscriptions),
        "notifications": inserted,
    }


def get_claim_cluster(
    *,
    cluster_id: int,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    cluster = db.get_claim_cluster(int(cluster_id))
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    if not principal.is_admin and str(cluster.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    count_row = db.execute_query(
        "SELECT COUNT(*) AS total FROM claim_cluster_membership WHERE cluster_id = ?",
        (int(cluster_id),),
    ).fetchone()
    size = int(count_row[0]) if count_row else 0
    payload = dict(cluster)
    counts = _load_watchlist_cluster_counts(str(cluster.get("user_id") or current_user.id), [int(cluster_id)])
    if counts:
        payload["watchlist_count"] = int(counts.get(int(cluster_id), payload.get("watchlist_count") or 0))
    payload["member_count"] = size
    return payload


def list_claim_cluster_links(
    *,
    cluster_id: int,
    direction: str,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_review(principal)
    cluster = db.get_claim_cluster(int(cluster_id))
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    if not principal.is_admin and str(cluster.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    rows = db.list_claim_cluster_links(cluster_id=int(cluster_id), direction=direction)
    links: List[Dict[str, Any]] = []
    for row in rows:
        parent_id = int(row.get("parent_cluster_id") or 0)
        child_id = int(row.get("child_cluster_id") or 0)
        if parent_id == int(cluster_id):
            direction_val = "outbound"
        elif child_id == int(cluster_id):
            direction_val = "inbound"
        else:
            direction_val = "unknown"
        links.append(
            {
                "parent_cluster_id": parent_id,
                "child_cluster_id": child_id,
                "relation_type": row.get("relation_type"),
                "created_at": row.get("created_at"),
                "direction": direction_val,
            }
        )
    return links


def create_claim_cluster_link(
    *,
    cluster_id: int,
    payload: Dict[str, Any],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    parent_id = int(cluster_id)
    child_id = int(payload.get("child_cluster_id"))
    if parent_id == child_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cluster link must be to a different cluster")
    parent = db.get_claim_cluster(parent_id)
    child = db.get_claim_cluster(child_id)
    if not parent or not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    if not principal.is_admin:
        if str(parent.get("user_id")) != str(current_user.id) or str(child.get("user_id")) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    created = db.create_claim_cluster_link(
        parent_cluster_id=parent_id,
        child_cluster_id=child_id,
        relation_type=payload.get("relation_type"),
    )
    if not created:
        created = {
            "parent_cluster_id": parent_id,
            "child_cluster_id": child_id,
            "relation_type": payload.get("relation_type"),
        }
    created["direction"] = "outbound"
    return created


def delete_claim_cluster_link(
    *,
    cluster_id: int,
    child_cluster_id: int,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    parent = db.get_claim_cluster(int(cluster_id))
    child = db.get_claim_cluster(int(child_cluster_id))
    if not parent or not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    if not principal.is_admin:
        if str(parent.get("user_id")) != str(current_user.id) or str(child.get("user_id")) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    deleted = db.delete_claim_cluster_link(
        parent_cluster_id=int(cluster_id),
        child_cluster_id=int(child_cluster_id),
    )
    return {
        "status": "deleted" if deleted else "missing",
        "parent_cluster_id": int(cluster_id),
        "child_cluster_id": int(child_cluster_id),
    }


def list_claim_cluster_members(
    *,
    cluster_id: int,
    limit: int,
    offset: int,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> List[Dict[str, Any]]:
    _ensure_claims_review(principal)
    cluster = db.get_claim_cluster(int(cluster_id))
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    if not principal.is_admin and str(cluster.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    rows = db.list_claim_cluster_members(int(cluster_id), limit=limit, offset=offset)
    return [_normalize_claim_row(dict(r)) for r in rows]


def evaluate_watchlist_cluster_notifications(
    *,
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        target_user_id = str(user_id) if user_id is not None else str(current_user.id)
        return _evaluate_watchlist_cluster_notifications(target_db, target_user_id)


def claim_cluster_timeline(
    *,
    cluster_id: int,
    limit: int,
    offset: int,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    cluster = db.get_claim_cluster(int(cluster_id))
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    if not principal.is_admin and str(cluster.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    rows = db.execute_query(
        "SELECT DATE(cluster_joined_at) AS day, COUNT(*) AS count "
        "FROM claim_cluster_membership WHERE cluster_id = ? "
        "GROUP BY day ORDER BY day ASC LIMIT ? OFFSET ?",
        (int(cluster_id), int(limit), int(offset)),
    ).fetchall()
    timeline = [{"day": r[0], "count": int(r[1])} for r in rows if r]
    return {"cluster_id": int(cluster_id), "timeline": timeline}


def claim_cluster_evidence(
    *,
    cluster_id: int,
    limit: int,
    offset: int,
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    _ensure_claims_review(principal)
    cluster = db.get_claim_cluster(int(cluster_id))
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    if not principal.is_admin and str(cluster.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    members = db.list_claim_cluster_members(int(cluster_id), limit=limit, offset=offset)
    buckets = {"supported": [], "refuted": [], "nei": []}
    for row in members:
        status_val = str(row.get("review_status") or "pending").lower()
        if status_val == "approved":
            buckets["supported"].append(_normalize_claim_row(dict(row)))
        elif status_val == "rejected":
            buckets["refuted"].append(_normalize_claim_row(dict(row)))
        else:
            buckets["nei"].append(_normalize_claim_row(dict(row)))

    counts = {k: len(v) for k, v in buckets.items()}
    return {
        "cluster_id": int(cluster_id),
        "counts": counts,
        "evidence": buckets,
    }


def list_claims_by_media(
    *,
    media_id: int,
    limit: int,
    offset: int,
    envelope: bool,
    absolute_links: bool,
    user_id: Optional[int],
    current_user: User,
    db: MediaDatabase,
    request: Any = None,
) -> Any:
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        claims = target_db.get_claims_by_media(media_id, limit=limit, offset=offset)
        if not envelope:
            return claims
        try:
            cur = target_db.execute_query(
                "SELECT COUNT(*) AS c FROM Claims WHERE media_id = ? AND deleted = 0",
                (media_id,),
            )
            row = cur.fetchone()
            total = int(row[0]) if row else 0
        except Exception:
            total = offset + len(claims)
        next_off: Optional[int] = None
        if offset + len(claims) < total:
            next_off = offset + len(claims)
        next_link: Optional[str] = None
        if next_off is not None:
            if request and absolute_links:
                base = f"{request.url.scheme}://{request.url.netloc}{request.url.path}"
            else:
                base = request.url.path if request else f"/api/v1/claims/{media_id}"
            params = f"limit={limit}&offset={next_off}&envelope=true"
            if user_id is not None and getattr(current_user, "is_admin", False):
                params += f"&user_id={int(user_id)}"
            if absolute_links:
                params += "&absolute_links=true"
            next_link = f"{base}?{params}"
        total_pages = int((total + int(limit) - 1) // int(limit)) if int(limit) > 0 else 0
        return {
            "items": claims,
            "next_offset": next_off,
            "total": total,
            "total_pages": total_pages,
            "next_link": next_link,
        }


def get_claim_item(
    *,
    claim_id: int,
    include_deleted: bool,
    user_id: Optional[int],
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        row = target_db.get_claim_with_media(int(claim_id), include_deleted=include_deleted)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
        return _normalize_claim_row(dict(row))


async def update_claim_item(
    *,
    claim_id: int,
    payload: Dict[str, Any],
    user_id: Optional[int],
    principal: AuthPrincipal,
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    with _resolve_media_db(
        db=db,
        current_user=current_user,
        user_id=user_id,
        admin_required=True,
        owner_filter=False,
    ) as (target_db, _owner_filter):
        claim_row = target_db.get_claim_with_media(int(claim_id), include_deleted=True)
        if not claim_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

        await _ensure_claim_edit_access(principal=principal, claim_row=claim_row)

        updated = target_db.update_claim(
            int(claim_id),
            claim_text=payload.get("claim_text"),
            span_start=payload.get("span_start"),
            span_end=payload.get("span_end"),
            confidence=payload.get("confidence"),
            extractor=payload.get("extractor"),
            extractor_version=payload.get("extractor_version"),
            deleted=payload.get("deleted"),
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
        if payload.get("claim_text") is not None:
            old_text = str(claim_row.get("claim_text") or "")
            new_text = str(payload.get("claim_text"))
            if new_text != old_text:
                target_user_id = str(user_id) if user_id is not None else str(current_user.id)
                _refresh_claim_embedding(
                    claim_id=int(claim_id),
                    media_id=int(claim_row.get("media_id") or 0),
                    chunk_index=int(claim_row.get("chunk_index") or 0),
                    old_text=old_text,
                    new_text=new_text,
                    user_id=target_user_id,
                )
        return _normalize_claim_row(dict(updated))


def rebuild_claims(
    *,
    media_id: int,
    user_id: Optional[int],
    current_user: User,
    db: MediaDatabase,
    rebuild_service: Any = None,
) -> Dict[str, Any]:
    if user_id is not None and getattr(current_user, "is_admin", False):
        db_path = get_user_media_db_path(int(user_id))
    else:
        db_path = db.db_path_str
    svc = rebuild_service or get_claims_rebuild_service()
    svc.submit(media_id=media_id, db_path=db_path)
    return {"status": "accepted", "media_id": media_id}


def rebuild_all_media(
    *,
    policy: str,
    user_id: Optional[int],
    current_user: User,
    db: MediaDatabase,
    rebuild_service: Any = None,
) -> Dict[str, Any]:
    override_db: Optional[MediaDatabase] = None
    try:
        if user_id is not None and getattr(current_user, "is_admin", False):
            db_path = get_user_media_db_path(int(user_id))
            override_db = MediaDatabase(
                db_path=db_path,
                client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
            )
            query_db = override_db
        else:
            db_path = db.db_path_str
            query_db = db

            svc = rebuild_service or get_claims_rebuild_service()

        policy = str(policy or "missing").lower()
        if policy == "all":
            sql = "SELECT id FROM Media WHERE deleted=0 AND is_trash=0"
            rows = query_db.execute_query(sql).fetchall()
        elif policy == "stale":
            sql = (
                "SELECT m.id FROM Media m "
                "LEFT JOIN (SELECT media_id, MAX(last_modified) AS lastc FROM Claims WHERE deleted=0 GROUP BY media_id) c ON c.media_id = m.id "
                "WHERE m.deleted=0 AND m.is_trash=0 AND (c.lastc IS NULL OR c.lastc < m.last_modified)"
            )
            rows = query_db.execute_query(sql).fetchall()
        else:
            sql = (
                "SELECT m.id FROM Media m "
                "WHERE m.deleted = 0 AND m.is_trash = 0 AND NOT EXISTS ("
                "  SELECT 1 FROM Claims c WHERE c.media_id = m.id AND c.deleted = 0"
                ")"
            )
            rows = query_db.execute_query(sql).fetchall()
        mids: list[int] = []
        for r in rows:
            try:
                mids.append(int(r["id"]))
            except Exception:
                try:
                    mids.append(int(r[0]))
                except Exception:
                    try:
                        if isinstance(r, dict):
                            first_val = next(iter(r.values()))
                            mids.append(int(first_val))
                    except Exception:
                        continue
        for mid in mids:
            svc.submit(media_id=mid, db_path=db_path)
        return {"status": "accepted", "enqueued": len(mids), "policy": policy}
    finally:
        if override_db is not None:
            try:
                override_db.close_connection()
            except Exception:
                pass


def rebuild_claims_fts(
    *,
    user_id: Optional[int],
    current_user: User,
    db: MediaDatabase,
) -> Dict[str, Any]:
    override_db: Optional[MediaDatabase] = None
    try:
        if user_id is not None and getattr(current_user, "is_admin", False):
            db_path = get_user_media_db_path(int(user_id))
            override_db = MediaDatabase(
                db_path=db_path,
                client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
            )
            count = override_db.rebuild_claims_fts()
        else:
            count = db.rebuild_claims_fts()
    finally:
        if override_db is not None:
            try:
                override_db.close_connection()
            except Exception:
                pass
    return {"status": "ok", "indexed": count}
