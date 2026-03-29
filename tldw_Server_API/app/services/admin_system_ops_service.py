from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from contextlib import contextmanager, suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from loguru import logger

from tldw_Server_API.app.core.Utils.Utils import get_database_dir

_FLAG_SCOPES = {"global", "org", "user"}
_INCIDENT_STATUSES = {"open", "investigating", "mitigating", "resolved"}
_INCIDENT_SEVERITIES = {"low", "medium", "high", "critical"}
_INCIDENT_ACTION_ITEM_LIMIT = 25
_INCIDENT_ACTION_ITEM_TEXT_MAX_LENGTH = 500
_UNSET = object()

_WEBHOOK_EVENTS = {
    "user.created",
    "user.deleted",
    "incident.created",
    "incident.updated",
    "incident.resolved",
}
_WEBHOOK_MAX_URL_LENGTH = 2048

_STORE_LOCK = Lock()
_STORE_PATH = Path(get_database_dir()) / "system_ops.json"
_LOCK_TIMEOUT_SECONDS = float(os.getenv("SYSTEM_OPS_LOCK_TIMEOUT", "5"))

_SYSTEM_OPS_NONCRITICAL_EXCEPTIONS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    json.JSONDecodeError,
)

try:
    import fcntl  # type: ignore

    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False


@contextmanager
def _store_file_lock(timeout: float = _LOCK_TIMEOUT_SECONDS):
    lock_path = _STORE_PATH.with_suffix(_STORE_PATH.suffix + ".lock")
    lock_fd = None
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        start_time = time.time()
        if _HAS_FCNTL:
            lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
            while True:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.time() - start_time > timeout:
                        raise RuntimeError(f"Failed to acquire system ops lock within {timeout}s") from None
                    time.sleep(0.05)
        else:
            while True:
                try:
                    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                    break
                except FileExistsError:
                    try:
                        lock_stat = os.stat(lock_path)
                        if time.time() - lock_stat.st_mtime > timeout * 2:
                            os.unlink(lock_path)
                            continue
                    except (OSError, FileNotFoundError):
                        pass
                    if time.time() - start_time > timeout:
                        raise RuntimeError(f"Failed to acquire system ops lock within {timeout}s") from None
                    time.sleep(0.05)
        yield
    finally:
        if lock_fd is not None:
            if _HAS_FCNTL:
                with suppress(_SYSTEM_OPS_NONCRITICAL_EXCEPTIONS):
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
            with suppress(_SYSTEM_OPS_NONCRITICAL_EXCEPTIONS):
                os.close(lock_fd)
        if not _HAS_FCNTL:
            with suppress(_SYSTEM_OPS_NONCRITICAL_EXCEPTIONS):
                lock_path.unlink(missing_ok=True)


@contextmanager
def _locked_store(write: bool = False):
    with _STORE_LOCK, _store_file_lock():
        store = _load_store()
        yield store
        if write:
            _save_store(store)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_store() -> dict[str, Any]:
    return {
        "maintenance": {
            "enabled": False,
            "message": "",
            "allowlist_user_ids": [],
            "allowlist_emails": [],
            "updated_at": None,
            "updated_by": None,
        },
        "feature_flags": [],
        "incidents": [],
        "webhooks": [],
        "webhook_deliveries": [],
        "invitations": [],
    }


def _parse_iso(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    raw = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _normalize_incident_action_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, Any]] = []
    for raw_item in value[:_INCIDENT_ACTION_ITEM_LIMIT]:
        if not isinstance(raw_item, dict):
            continue
        text = str(raw_item.get("text") or "").strip()
        if not text:
            continue
        normalized.append(
            {
                "id": str(raw_item.get("id") or f"ai_{uuid4().hex[:10]}"),
                "text": text[:_INCIDENT_ACTION_ITEM_TEXT_MAX_LENGTH],
                "done": bool(raw_item.get("done")),
            }
        )
    return normalized


def _normalize_incident_record(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("invalid_incident")

    incident = dict(value)
    incident["assigned_to_user_id"] = (
        int(incident["assigned_to_user_id"])
        if incident.get("assigned_to_user_id") is not None
        else None
    )
    incident["assigned_to_label"] = (
        str(incident["assigned_to_label"]).strip() or None
        if incident.get("assigned_to_label") is not None
        else None
    )
    incident["root_cause"] = (
        str(incident["root_cause"]).strip() or None
        if incident.get("root_cause") is not None
        else None
    )
    incident["impact"] = (
        str(incident["impact"]).strip() or None
        if incident.get("impact") is not None
        else None
    )
    incident["action_items"] = _normalize_incident_action_items(incident.get("action_items"))
    incident.setdefault("acknowledged_at", None)
    return incident


def _load_store() -> dict[str, Any]:
    if not _STORE_PATH.exists():
        return _default_store()
    try:
        raw = _STORE_PATH.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
    except _SYSTEM_OPS_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning("System ops store unreadable: {}", exc)
        return _default_store()
    if not isinstance(data, dict):
        return _default_store()
    data.setdefault("maintenance", _default_store()["maintenance"])
    data.setdefault("feature_flags", [])
    data.setdefault("incidents", [])
    data.setdefault("webhooks", [])
    data.setdefault("webhook_deliveries", [])
    data.setdefault("invitations", [])
    return data


def _save_store(store: dict[str, Any]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps(store, indent=2, sort_keys=False), encoding="utf-8")


def _normalize_flag_scope(scope: str) -> str:
    value = (scope or "").strip().lower()
    if value not in _FLAG_SCOPES:
        raise ValueError("invalid_scope")
    return value


def _normalize_rollout_percent(value: Any, *, strict: bool) -> int:
    if value is None:
        return 100
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        if strict:
            raise ValueError("invalid_rollout_percent") from None
        return 100
    if 0 <= parsed <= 100:
        return parsed
    if strict:
        raise ValueError("invalid_rollout_percent")
    return 100


def _normalize_allowlist_ids(values: list[int] | None) -> list[int]:
    if not values:
        return []
    cleaned = []
    for val in values:
        try:
            cleaned.append(int(val))
        except (TypeError, ValueError):
            continue
    return sorted(set(cleaned))


def _normalize_allowlist_emails(values: list[str] | None) -> list[str]:
    if not values:
        return []
    cleaned = []
    for val in values:
        if not val:
            continue
        cleaned.append(str(val).strip().lower())
    return sorted({val for val in cleaned if val})


def _normalize_target_user_ids(values: list[int] | None) -> list[int]:
    if not isinstance(values, list):
        return []
    cleaned = _normalize_allowlist_ids(values)
    return [value for value in cleaned if value > 0]


def _normalize_variant_value(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _build_flag_snapshot(flag: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope": _normalize_flag_scope(str(flag.get("scope") or "global")),
        "enabled": bool(flag.get("enabled")),
        "org_id": flag.get("org_id"),
        "user_id": flag.get("user_id"),
        "target_user_ids": _normalize_target_user_ids(flag.get("target_user_ids")),
        "rollout_percent": _normalize_rollout_percent(flag.get("rollout_percent"), strict=False),
        "variant_value": _normalize_variant_value(flag.get("variant_value")),
    }


def _normalize_flag_snapshot(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    scope = value.get("scope")
    if scope is None:
        return None
    try:
        normalized_scope = _normalize_flag_scope(str(scope))
    except ValueError:
        return None
    return {
        "scope": normalized_scope,
        "enabled": bool(value.get("enabled")),
        "org_id": value.get("org_id"),
        "user_id": value.get("user_id"),
        "target_user_ids": _normalize_target_user_ids(value.get("target_user_ids")),
        "rollout_percent": _normalize_rollout_percent(value.get("rollout_percent"), strict=False),
        "variant_value": _normalize_variant_value(value.get("variant_value")),
    }


def _normalize_feature_flag_record(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("invalid_feature_flag")
    key = str(value.get("key") or "").strip()
    if not key:
        raise ValueError("invalid_feature_flag")
    scope = _normalize_flag_scope(str(value.get("scope") or "global"))
    normalized = {
        "key": key,
        "scope": scope,
        "enabled": bool(value.get("enabled")),
        "description": (str(value.get("description")).strip() if value.get("description") else None),
        "org_id": value.get("org_id"),
        "user_id": value.get("user_id"),
        "target_user_ids": _normalize_target_user_ids(value.get("target_user_ids")),
        "rollout_percent": _normalize_rollout_percent(value.get("rollout_percent"), strict=False),
        "variant_value": _normalize_variant_value(value.get("variant_value")),
        "created_at": value.get("created_at"),
        "updated_at": value.get("updated_at"),
        "updated_by": value.get("updated_by"),
        "history": [],
    }
    history: list[dict[str, Any]] = []
    for entry in value.get("history") or []:
        if not isinstance(entry, dict):
            continue
        history.append(
            {
                "timestamp": entry.get("timestamp") or normalized["updated_at"] or _now_iso(),
                "enabled": bool(entry.get("enabled", normalized["enabled"])),
                "actor": entry.get("actor"),
                "note": (str(entry.get("note")).strip() if entry.get("note") else None),
                "before": _normalize_flag_snapshot(entry.get("before")),
                "after": _normalize_flag_snapshot(entry.get("after")),
            }
        )
    normalized["history"] = history
    return normalized


def get_maintenance_state() -> dict[str, Any]:
    with _locked_store() as store:
        return dict(store["maintenance"])


def update_maintenance_state(
    *,
    enabled: bool,
    message: str | None,
    allowlist_user_ids: list[int] | None,
    allowlist_emails: list[str] | None,
    actor: str | None,
) -> dict[str, Any]:
    with _locked_store(write=True) as store:
        maintenance = store["maintenance"]
        maintenance["enabled"] = bool(enabled)
        maintenance["message"] = (message or "").strip()
        maintenance["allowlist_user_ids"] = _normalize_allowlist_ids(allowlist_user_ids)
        maintenance["allowlist_emails"] = _normalize_allowlist_emails(allowlist_emails)
        maintenance["updated_at"] = _now_iso()
        maintenance["updated_by"] = actor
        store["maintenance"] = maintenance
        return dict(maintenance)


def list_feature_flags(
    *,
    scope: str | None = None,
    org_id: int | None = None,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    with _locked_store() as store:
        flags_raw = list(store.get("feature_flags", []))
    flags = []
    for flag in flags_raw:
        try:
            flags.append(_normalize_feature_flag_record(flag))
        except ValueError:
            continue
    if scope:
        scope_norm = _normalize_flag_scope(scope)
        if scope_norm == "org" and org_id is None:
            raise ValueError("missing_org_id")
        if scope_norm == "user" and user_id is None:
            raise ValueError("missing_user_id")
        flags = [flag for flag in flags if flag.get("scope") == scope_norm]
    if org_id is not None:
        flags = [flag for flag in flags if flag.get("org_id") == org_id]
    if user_id is not None:
        flags = [flag for flag in flags if flag.get("user_id") == user_id]
    flags.sort(key=lambda item: (item.get("key") or "", item.get("scope") or ""))
    return flags


def upsert_feature_flag(
    *,
    key: str,
    scope: str,
    enabled: bool,
    description: str | None,
    org_id: int | None,
    user_id: int | None,
    target_user_ids: list[int] | None,
    rollout_percent: int | None,
    variant_value: str | None,
    actor: str | None,
    note: str | None,
) -> dict[str, Any]:
    normalized_key = (key or "").strip()
    if not normalized_key:
        raise ValueError("invalid_key")
    scope_norm = _normalize_flag_scope(scope)
    if scope_norm == "org" and org_id is None:
        raise ValueError("missing_org_id")
    if scope_norm == "user" and user_id is None:
        raise ValueError("missing_user_id")
    normalized_target_user_ids = _normalize_target_user_ids(target_user_ids)
    normalized_rollout_percent = _normalize_rollout_percent(rollout_percent, strict=True)
    normalized_variant_value = _normalize_variant_value(variant_value)

    now = _now_iso()
    with _locked_store(write=True) as store:
        flags = store.get("feature_flags", [])
        for flag in flags:
            if (
                flag.get("key") == normalized_key
                and flag.get("scope") == scope_norm
                and flag.get("org_id") == org_id
                and flag.get("user_id") == user_id
            ):
                before_state = _build_flag_snapshot(_normalize_feature_flag_record(flag))
                flag["enabled"] = bool(enabled)
                if description is not None:
                    flag["description"] = description.strip() or None
                flag["target_user_ids"] = normalized_target_user_ids
                flag["rollout_percent"] = normalized_rollout_percent
                flag["variant_value"] = normalized_variant_value
                flag["updated_at"] = now
                flag["updated_by"] = actor
                after_state = _build_flag_snapshot(flag)
                history_entry = {
                    "timestamp": now,
                    "enabled": bool(enabled),
                    "actor": actor,
                    "note": (note or "").strip() or None,
                    "before": before_state,
                    "after": after_state,
                }
                flag.setdefault("history", []).append(history_entry)
                return _normalize_feature_flag_record(flag)

        new_flag = {
            "key": normalized_key,
            "scope": scope_norm,
            "enabled": bool(enabled),
            "description": description.strip() if description else None,
            "org_id": org_id,
            "user_id": user_id,
            "target_user_ids": normalized_target_user_ids,
            "rollout_percent": normalized_rollout_percent,
            "variant_value": normalized_variant_value,
            "created_at": now,
            "updated_at": now,
            "updated_by": actor,
            "history": [],
        }
        history_entry = {
            "timestamp": now,
            "enabled": bool(enabled),
            "actor": actor,
            "note": (note or "").strip() or None,
            "before": None,
            "after": _build_flag_snapshot(new_flag),
        }
        new_flag["history"].append(history_entry)
        flags.append(new_flag)
        store["feature_flags"] = flags
        return _normalize_feature_flag_record(new_flag)


def delete_feature_flag(
    *,
    key: str,
    scope: str,
    org_id: int | None,
    user_id: int | None,
) -> None:
    normalized_key = (key or "").strip()
    scope_norm = _normalize_flag_scope(scope)
    if scope_norm == "org" and org_id is None:
        raise ValueError("missing_org_id")
    if scope_norm == "user" and user_id is None:
        raise ValueError("missing_user_id")
    with _locked_store(write=True) as store:
        flags = store.get("feature_flags", [])
        remaining = [
            flag
            for flag in flags
            if not (
                flag.get("key") == normalized_key
                and flag.get("scope") == scope_norm
                and flag.get("org_id") == org_id
                and flag.get("user_id") == user_id
            )
        ]
        if len(remaining) == len(flags):
            raise ValueError("not_found")
        store["feature_flags"] = remaining


def list_incidents(
    *,
    status: str | None,
    severity: str | None,
    tag: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    with _locked_store() as store:
        incidents = list(store.get("incidents", []))
    if status:
        status_norm = status.strip().lower()
        incidents = [item for item in incidents if item.get("status") == status_norm]
    if severity:
        severity_norm = severity.strip().lower()
        incidents = [item for item in incidents if item.get("severity") == severity_norm]
    if tag:
        tag_norm = tag.strip().lower()
        incidents = [
            item for item in incidents if tag_norm in {t.lower() for t in (item.get("tags") or [])}
        ]
    incidents.sort(key=lambda item: _parse_iso(item.get("updated_at")), reverse=True)
    total = len(incidents)
    safe_offset = max(0, offset)
    safe_limit = max(1, limit)
    items = [
        _normalize_incident_record(item)
        for item in incidents[safe_offset:safe_offset + safe_limit]
    ]
    for inc in items:
        inc["mtta_minutes"] = None
        inc["mttr_minutes"] = None
        created = inc.get("created_at")
        acknowledged = inc.get("acknowledged_at")
        resolved = inc.get("resolved_at")
        if created and acknowledged:
            try:
                c = datetime.fromisoformat(str(created))
                a = datetime.fromisoformat(str(acknowledged))
                val = (a - c).total_seconds() / 60
                if val >= 0:
                    inc["mtta_minutes"] = round(val, 1)
            except (ValueError, TypeError):
                pass
        if created and resolved:
            try:
                c = datetime.fromisoformat(str(created))
                r = datetime.fromisoformat(str(resolved))
                val = (r - c).total_seconds() / 60
                if val >= 0:
                    inc["mttr_minutes"] = round(val, 1)
            except (ValueError, TypeError):
                pass
    return items, total


def create_incident(
    *,
    title: str,
    status: str | None,
    severity: str | None,
    summary: str | None,
    tags: list[str] | None,
    actor: str | None,
) -> dict[str, Any]:
    title_norm = (title or "").strip()
    if not title_norm:
        raise ValueError("invalid_title")
    status_norm = (status or "open").strip().lower()
    severity_norm = (severity or "medium").strip().lower()
    if status_norm not in _INCIDENT_STATUSES:
        raise ValueError("invalid_status")
    if severity_norm not in _INCIDENT_SEVERITIES:
        raise ValueError("invalid_severity")
    now = _now_iso()
    incident_id = f"inc_{uuid4().hex[:10]}"
    resolved_at = now if status_norm == "resolved" else None
    timeline_entry = {
        "id": f"evt_{uuid4().hex[:10]}",
        "message": "Incident created",
        "created_at": now,
        "actor": actor,
    }
    acknowledged_at = now if status_norm != "open" else None
    incident = {
        "id": incident_id,
        "title": title_norm,
        "status": status_norm,
        "severity": severity_norm,
        "summary": (summary or "").strip() or None,
        "tags": tags or [],
        "created_at": now,
        "updated_at": now,
        "resolved_at": resolved_at,
        "acknowledged_at": acknowledged_at,
        "created_by": actor,
        "updated_by": actor,
        "timeline": [timeline_entry],
        "assigned_to_user_id": None,
        "assigned_to_label": None,
        "root_cause": None,
        "impact": None,
        "action_items": [],
    }
    with _locked_store(write=True) as store:
        store.setdefault("incidents", []).append(incident)
    return _normalize_incident_record(incident)


def update_incident(
    *,
    incident_id: str,
    title: str | None,
    status: str | None,
    severity: str | None,
    summary: str | None,
    tags: list[str] | None,
    assigned_to_user_id: Any = _UNSET,
    assigned_to_label: Any = _UNSET,
    root_cause: Any = _UNSET,
    impact: Any = _UNSET,
    action_items: Any = _UNSET,
    update_message: str | None,
    actor: str | None,
) -> dict[str, Any]:
    now = _now_iso()
    note = (update_message or "").strip() or None
    with _locked_store(write=True) as store:
        incidents = store.get("incidents", [])
        for index, incident in enumerate(incidents):
            if incident.get("id") != incident_id:
                continue
            current = _normalize_incident_record(incident)
            updated_incident = dict(current)
            updated_incident["tags"] = list(current.get("tags") or [])
            updated_incident["timeline"] = list(current.get("timeline") or [])
            updated_incident["action_items"] = [dict(item) for item in current.get("action_items") or []]
            if title is not None:
                updated_incident["title"] = title.strip() or current.get("title")
            if status is not None:
                status_norm = status.strip().lower()
                if status_norm not in _INCIDENT_STATUSES:
                    raise ValueError("invalid_status")
                if current.get("status") == "open" and status_norm != "open" and not current.get("acknowledged_at"):
                    updated_incident["acknowledged_at"] = now
                updated_incident["status"] = status_norm
                updated_incident["resolved_at"] = now if status_norm == "resolved" else None
            if severity is not None:
                severity_norm = severity.strip().lower()
                if severity_norm not in _INCIDENT_SEVERITIES:
                    raise ValueError("invalid_severity")
                updated_incident["severity"] = severity_norm
            if summary is not None:
                updated_incident["summary"] = summary.strip() or None
            if tags is not None:
                updated_incident["tags"] = tags
            if assigned_to_user_id is not _UNSET:
                if assigned_to_user_id is None:
                    updated_incident["assigned_to_user_id"] = None
                    updated_incident["assigned_to_label"] = None
                else:
                    updated_incident["assigned_to_user_id"] = int(assigned_to_user_id)
                    updated_incident["assigned_to_label"] = (
                        str(assigned_to_label).strip() or None
                        if assigned_to_label is not None and assigned_to_label is not _UNSET
                        else None
                    )
            if root_cause is not _UNSET:
                updated_incident["root_cause"] = (
                    str(root_cause).strip() or None
                    if root_cause is not None
                    else None
                )
            if impact is not _UNSET:
                updated_incident["impact"] = (
                    str(impact).strip() or None
                    if impact is not None
                    else None
                )
            if action_items is not _UNSET:
                updated_incident["action_items"] = _normalize_incident_action_items(action_items)
            if note:
                updated_incident.setdefault("timeline", []).append(
                    {
                        "id": f"evt_{uuid4().hex[:10]}",
                        "message": note,
                        "created_at": now,
                        "actor": actor,
                    }
                )
            updated_incident["updated_at"] = now
            updated_incident["updated_by"] = actor
            incidents[index] = updated_incident
            return _normalize_incident_record(updated_incident)
    raise ValueError("not_found")


def add_incident_event(
    *,
    incident_id: str,
    message: str,
    actor: str | None,
) -> dict[str, Any]:
    note = (message or "").strip()
    if not note:
        raise ValueError("invalid_message")
    now = _now_iso()
    with _locked_store(write=True) as store:
        incidents = store.get("incidents", [])
        for incident in incidents:
            if incident.get("id") != incident_id:
                continue
            event = {
                "id": f"evt_{uuid4().hex[:10]}",
                "message": note,
                "created_at": now,
                "actor": actor,
            }
            incident.setdefault("timeline", []).append(event)
            incident["updated_at"] = now
            incident["updated_by"] = actor
            return _normalize_incident_record(incident)
    raise ValueError("not_found")


def delete_incident(*, incident_id: str) -> None:
    with _locked_store(write=True) as store:
        incidents = store.get("incidents", [])
        remaining = [item for item in incidents if item.get("id") != incident_id]
        if len(remaining) == len(incidents):
            raise ValueError("not_found")
        store["incidents"] = remaining


# -----------------------------------------------------------------------------------------------------------------
# Webhooks
# -----------------------------------------------------------------------------------------------------------------


def _normalize_webhook_record(value: Any) -> dict[str, Any]:
    """Normalize a raw webhook dict from the store."""
    if not isinstance(value, dict):
        raise ValueError("invalid_webhook")
    return {
        "id": str(value.get("id") or ""),
        "url": str(value.get("url") or ""),
        "events": list(value.get("events") or []),
        "enabled": bool(value.get("enabled", True)),
        "created_at": value.get("created_at"),
        "updated_at": value.get("updated_at"),
    }


def _redact_webhook(webhook: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the webhook with the secret removed (for list responses)."""
    result = dict(webhook)
    result.pop("secret", None)
    return result


def list_webhooks() -> list[dict[str, Any]]:
    """Return all webhooks with secrets redacted."""
    with _locked_store() as store:
        webhooks_raw = list(store.get("webhooks", []))
    webhooks = []
    for webhook in webhooks_raw:
        try:
            webhooks.append(_redact_webhook(_normalize_webhook_record(webhook)))
        except ValueError:
            continue
    webhooks.sort(key=lambda item: item.get("created_at") or "")
    return webhooks


def create_webhook(
    *,
    url: str,
    events: list[str],
    enabled: bool = True,
) -> dict[str, Any]:
    """Create a new webhook and return it with the secret included (shown once)."""
    url_norm = (url or "").strip()
    if not url_norm:
        raise ValueError("invalid_url")
    if len(url_norm) > _WEBHOOK_MAX_URL_LENGTH:
        raise ValueError("invalid_url")
    if not url_norm.startswith(("http://", "https://")):
        raise ValueError("invalid_url")

    events_norm = sorted({e.strip().lower() for e in (events or []) if e and e.strip()})
    if not events_norm:
        raise ValueError("invalid_events")
    invalid_events = set(events_norm) - _WEBHOOK_EVENTS
    if invalid_events:
        raise ValueError("invalid_events")

    now = _now_iso()
    webhook_id = f"wh_{uuid4().hex[:10]}"
    secret = secrets.token_hex(32)
    webhook = {
        "id": webhook_id,
        "url": url_norm,
        "secret": secret,
        "events": events_norm,
        "enabled": bool(enabled),
        "created_at": now,
        "updated_at": now,
    }
    with _locked_store(write=True) as store:
        store.setdefault("webhooks", []).append(webhook)
    # Return with secret so caller can show it once
    return dict(webhook)


def update_webhook(
    *,
    webhook_id: str,
    url: str | None = None,
    events: list[str] | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """Update a webhook. Returns the webhook with secret redacted."""
    now = _now_iso()
    with _locked_store(write=True) as store:
        webhooks = store.get("webhooks", [])
        for webhook in webhooks:
            if webhook.get("id") != webhook_id:
                continue
            if url is not None:
                url_norm = url.strip()
                if not url_norm:
                    raise ValueError("invalid_url")
                if len(url_norm) > _WEBHOOK_MAX_URL_LENGTH:
                    raise ValueError("invalid_url")
                if not url_norm.startswith(("http://", "https://")):
                    raise ValueError("invalid_url")
                webhook["url"] = url_norm
            if events is not None:
                events_norm = sorted({e.strip().lower() for e in events if e and e.strip()})
                if not events_norm:
                    raise ValueError("invalid_events")
                invalid = set(events_norm) - _WEBHOOK_EVENTS
                if invalid:
                    raise ValueError("invalid_events")
                webhook["events"] = events_norm
            if enabled is not None:
                webhook["enabled"] = bool(enabled)
            webhook["updated_at"] = now
            return _redact_webhook(_normalize_webhook_record(webhook))
    raise ValueError("not_found")


def delete_webhook(*, webhook_id: str) -> None:
    """Delete a webhook by ID."""
    with _locked_store(write=True) as store:
        webhooks = store.get("webhooks", [])
        remaining = [item for item in webhooks if item.get("id") != webhook_id]
        if len(remaining) == len(webhooks):
            raise ValueError("not_found")
        store["webhooks"] = remaining


# ──────────────────────────────────────────────────────────────────────────────
# Webhook Delivery Log
# ──────────────────────────────────────────────────────────────────────────────

_WEBHOOK_DELIVERIES_CAP = 1000


def _get_webhook_with_secret(webhook_id: str) -> dict[str, Any]:
    """Return a webhook record including its secret. Raises ValueError if not found."""
    with _locked_store() as store:
        for webhook in store.get("webhooks", []):
            if webhook.get("id") == webhook_id:
                return dict(webhook)
    raise ValueError("not_found")


def record_webhook_delivery(
    *,
    webhook_id: str,
    event_type: str,
    status_code: int | None,
    response_time_ms: int | None,
    success: bool,
    error: str | None = None,
    payload_preview: str | None = None,
) -> dict[str, Any]:
    """Append a delivery record for a webhook. Prunes oldest entries beyond cap."""
    now = _now_iso()
    record = {
        "id": f"wd_{uuid4().hex[:12]}",
        "webhook_id": str(webhook_id),
        "event_type": str(event_type or ""),
        "status_code": int(status_code) if status_code is not None else None,
        "response_time_ms": int(response_time_ms) if response_time_ms is not None else None,
        "success": bool(success),
        "error": str(error)[:500] if error else None,
        "attempted_at": now,
        "payload_preview": str(payload_preview)[:500] if payload_preview else None,
    }
    with _locked_store(write=True) as store:
        deliveries = store.setdefault("webhook_deliveries", [])
        deliveries.append(record)
        # Keep only the most recent entries per webhook (prune oldest)
        wh_deliveries = [d for d in deliveries if d.get("webhook_id") == webhook_id]
        if len(wh_deliveries) > _WEBHOOK_DELIVERIES_CAP:
            excess = len(wh_deliveries) - _WEBHOOK_DELIVERIES_CAP
            # Remove the oldest excess entries for this webhook
            removed = 0
            pruned: list[dict[str, Any]] = []
            for d in deliveries:
                if d.get("webhook_id") == webhook_id and removed < excess:
                    removed += 1
                    continue
                pruned.append(d)
            store["webhook_deliveries"] = pruned
    return record


def list_webhook_deliveries(
    *,
    webhook_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return delivery records for a webhook, newest first."""
    limit = max(1, min(limit, _WEBHOOK_DELIVERIES_CAP))
    with _locked_store() as store:
        deliveries = store.get("webhook_deliveries", [])
        wh_deliveries = [d for d in deliveries if d.get("webhook_id") == webhook_id]
    # Sort newest first
    wh_deliveries.sort(key=lambda d: d.get("attempted_at") or "", reverse=True)
    return wh_deliveries[:limit]


def send_test_webhook(*, webhook_id: str) -> dict[str, Any]:
    """Send a test payload to a webhook URL with HMAC signing and record the delivery.

    Returns the delivery record.
    """
    import httpx

    webhook = _get_webhook_with_secret(webhook_id)
    url = webhook.get("url", "")
    secret = webhook.get("secret", "")

    test_payload = {
        "event": "webhook.test",
        "webhook_id": webhook_id,
        "timestamp": _now_iso(),
        "data": {"message": "This is a test delivery from the admin panel."},
    }

    body_bytes = json.dumps(test_payload, separators=(",", ":")).encode("utf-8")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if secret:
        sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={sig}"

    status_code: int | None = None
    success = False
    error_msg: str | None = None
    start = time.monotonic()

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, content=body_bytes, headers=headers)
            status_code = resp.status_code
            success = 200 <= resp.status_code < 300
            if not success:
                error_msg = f"HTTP {resp.status_code}"
    except _SYSTEM_OPS_NONCRITICAL_EXCEPTIONS as exc:
        error_msg = str(exc)[:500]
    except Exception as exc:
        error_msg = str(exc)[:500]

    elapsed_ms = int((time.monotonic() - start) * 1000)

    delivery = record_webhook_delivery(
        webhook_id=webhook_id,
        event_type="webhook.test",
        status_code=status_code,
        response_time_ms=elapsed_ms,
        success=success,
        error=error_msg,
        payload_preview=json.dumps(test_payload)[:500],
    )
    return delivery


# ──────────────────────────────────────────────────────────────────────────────
# User Invitations
# ──────────────────────────────────────────────────────────────────────────────

_INVITATION_STATUSES = {"pending", "accepted", "expired", "revoked"}
_INVITATION_ROLES = {"user", "admin", "service", "viewer"}
_INVITATION_DEFAULT_EXPIRY_DAYS = 7
_INVITATION_MAX_PENDING = 200


def _normalize_invitation_record(value: Any) -> dict[str, Any]:
    """Normalize and validate an invitation record."""
    if not isinstance(value, dict):
        raise ValueError("invalid_invitation")
    invitation = dict(value)
    invitation.setdefault("id", uuid4().hex[:16])
    invitation.setdefault("status", "pending")
    invitation.setdefault("created_at", _now_iso())
    invitation.setdefault("accepted_at", None)
    invitation.setdefault("email_sent", False)
    invitation.setdefault("email_error", None)
    return invitation


def list_invitations(
    *,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List all user invitations, optionally filtered by status."""
    with _locked_store() as store:
        invitations_raw = list(store.get("invitations", []))

    invitations = []
    now = datetime.now(timezone.utc)
    for inv in invitations_raw:
        try:
            record = _normalize_invitation_record(inv)
        except ValueError:
            continue
        # Auto-expire pending invitations past their expiry date
        if record["status"] == "pending":
            expires_at = record.get("expires_at")
            if expires_at:
                expiry_dt = _parse_iso(expires_at)
                if expiry_dt < now:
                    record["status"] = "expired"
        invitations.append(record)

    if status:
        status_norm = status.strip().lower()
        if status_norm in _INVITATION_STATUSES:
            invitations = [inv for inv in invitations if inv.get("status") == status_norm]

    invitations.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return invitations


def create_invitation(
    *,
    email: str,
    role: str = "user",
    invited_by: str | None = None,
    expiry_days: int = _INVITATION_DEFAULT_EXPIRY_DAYS,
) -> dict[str, Any]:
    """Create a new user invitation."""
    email_norm = (email or "").strip().lower()
    if not email_norm or "@" not in email_norm:
        raise ValueError("invalid_email")

    role_norm = (role or "user").strip().lower()
    if role_norm not in _INVITATION_ROLES:
        raise ValueError("invalid_role")

    if expiry_days < 1 or expiry_days > 365:
        expiry_days = _INVITATION_DEFAULT_EXPIRY_DAYS

    token = secrets.token_urlsafe(32)
    now = _now_iso()
    now_dt = datetime.now(timezone.utc)
    expires_at = (now_dt + timedelta(days=expiry_days)).isoformat()

    invitation = {
        "id": uuid4().hex[:16],
        "email": email_norm,
        "role": role_norm,
        "status": "pending",
        "token": token,
        "invited_by": invited_by,
        "created_at": now,
        "expires_at": expires_at,
        "accepted_at": None,
        "email_sent": False,
        "email_error": None,
    }

    with _locked_store(write=True) as store:
        invitations = store.get("invitations", [])

        # Check for duplicate pending invitation to same email
        for existing in invitations:
            if (
                existing.get("email") == email_norm
                and existing.get("status") == "pending"
            ):
                expires_at_existing = existing.get("expires_at")
                if expires_at_existing:
                    expiry_dt = _parse_iso(expires_at_existing)
                    if expiry_dt > now_dt:
                        raise ValueError("duplicate_pending_invitation")

        # Cap total pending invitations
        pending_count = sum(1 for inv in invitations if inv.get("status") == "pending")
        if pending_count >= _INVITATION_MAX_PENDING:
            raise ValueError("too_many_pending_invitations")

        invitations.append(invitation)
        store["invitations"] = invitations

    return invitation


def get_invitation_by_token(*, token: str) -> dict[str, Any] | None:
    """Look up an invitation by its token."""
    with _locked_store() as store:
        for inv in store.get("invitations", []):
            if inv.get("token") == token:
                return _normalize_invitation_record(inv)
    return None


def update_invitation_email_status(
    *,
    invitation_id: str,
    email_sent: bool,
    email_error: str | None = None,
) -> dict[str, Any] | None:
    """Update the email delivery status for an invitation."""
    with _locked_store(write=True) as store:
        invitations = store.get("invitations", [])
        for inv in invitations:
            if inv.get("id") == invitation_id:
                inv["email_sent"] = email_sent
                inv["email_error"] = email_error
                return _normalize_invitation_record(inv)
    return None


def revoke_invitation(*, invitation_id: str) -> dict[str, Any]:
    """Revoke a pending invitation."""
    with _locked_store(write=True) as store:
        invitations = store.get("invitations", [])
        for inv in invitations:
            if inv.get("id") == invitation_id:
                if inv.get("status") != "pending":
                    raise ValueError("not_pending")
                inv["status"] = "revoked"
                return _normalize_invitation_record(inv)
    raise ValueError("not_found")


def accept_invitation(*, invitation_id: str) -> dict[str, Any]:
    """Mark an invitation as accepted."""
    with _locked_store(write=True) as store:
        invitations = store.get("invitations", [])
        for inv in invitations:
            if inv.get("id") == invitation_id:
                if inv.get("status") != "pending":
                    raise ValueError("not_pending")
                inv["status"] = "accepted"
                inv["accepted_at"] = _now_iso()
                return _normalize_invitation_record(inv)
    raise ValueError("not_found")
