from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from loguru import logger

from tldw_Server_API.app.core.Utils.Utils import get_database_dir


_FLAG_SCOPES = {"global", "org", "user"}
_INCIDENT_STATUSES = {"open", "investigating", "mitigating", "resolved"}
_INCIDENT_SEVERITIES = {"low", "medium", "high", "critical"}

_STORE_LOCK = Lock()
_STORE_PATH = Path(get_database_dir()) / "system_ops.json"
_LOCK_TIMEOUT_SECONDS = float(os.getenv("SYSTEM_OPS_LOCK_TIMEOUT", "5"))

try:
    import fcntl  # type: ignore

    _HAS_FCNTL = True
except Exception:
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
                except (IOError, OSError):
                    if time.time() - start_time > timeout:
                        raise RuntimeError(f"Failed to acquire system ops lock within {timeout}s")
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
                        raise RuntimeError(f"Failed to acquire system ops lock within {timeout}s")
                    time.sleep(0.05)
        yield
    finally:
        if lock_fd is not None:
            if _HAS_FCNTL:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                except Exception:
                    pass
            try:
                os.close(lock_fd)
            except Exception:
                pass
        if not _HAS_FCNTL:
            try:
                lock_path.unlink(missing_ok=True)
            except Exception:
                pass


@contextmanager
def _locked_store(write: bool = False):
    with _STORE_LOCK:
        with _store_file_lock():
            store = _load_store()
            yield store
            if write:
                _save_store(store)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_store() -> Dict[str, Any]:
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
    }


def _parse_iso(value: Optional[str]) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    raw = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _load_store() -> Dict[str, Any]:
    if not _STORE_PATH.exists():
        return _default_store()
    try:
        raw = _STORE_PATH.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        logger.warning("System ops store unreadable: {}", exc)
        return _default_store()
    if not isinstance(data, dict):
        return _default_store()
    data.setdefault("maintenance", _default_store()["maintenance"])
    data.setdefault("feature_flags", [])
    data.setdefault("incidents", [])
    return data


def _save_store(store: Dict[str, Any]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps(store, indent=2, sort_keys=False), encoding="utf-8")


def _normalize_flag_scope(scope: str) -> str:
    value = (scope or "").strip().lower()
    if value not in _FLAG_SCOPES:
        raise ValueError("invalid_scope")
    return value


def _normalize_allowlist_ids(values: Optional[List[int]]) -> List[int]:
    if not values:
        return []
    cleaned = []
    for val in values:
        try:
            cleaned.append(int(val))
        except (TypeError, ValueError):
            continue
    return sorted(set(cleaned))


def _normalize_allowlist_emails(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    cleaned = []
    for val in values:
        if not val:
            continue
        cleaned.append(str(val).strip().lower())
    return sorted({val for val in cleaned if val})


def get_maintenance_state() -> Dict[str, Any]:
    with _locked_store() as store:
        return dict(store["maintenance"])


def update_maintenance_state(
    *,
    enabled: bool,
    message: Optional[str],
    allowlist_user_ids: Optional[List[int]],
    allowlist_emails: Optional[List[str]],
    actor: Optional[str],
) -> Dict[str, Any]:
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
    scope: Optional[str] = None,
    org_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    with _locked_store() as store:
        flags = list(store.get("feature_flags", []))
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
    description: Optional[str],
    org_id: Optional[int],
    user_id: Optional[int],
    actor: Optional[str],
    note: Optional[str],
) -> Dict[str, Any]:
    normalized_key = (key or "").strip()
    if not normalized_key:
        raise ValueError("invalid_key")
    scope_norm = _normalize_flag_scope(scope)
    if scope_norm == "org" and org_id is None:
        raise ValueError("missing_org_id")
    if scope_norm == "user" and user_id is None:
        raise ValueError("missing_user_id")

    now = _now_iso()
    with _locked_store(write=True) as store:
        flags = store.get("feature_flags", [])
        history_entry = {
            "timestamp": now,
            "enabled": bool(enabled),
            "actor": actor,
            "note": (note or "").strip() or None,
        }
        for flag in flags:
            if (
                flag.get("key") == normalized_key
                and flag.get("scope") == scope_norm
                and flag.get("org_id") == org_id
                and flag.get("user_id") == user_id
            ):
                flag["enabled"] = bool(enabled)
                if description is not None:
                    flag["description"] = description.strip() or None
                flag["updated_at"] = now
                flag["updated_by"] = actor
                flag.setdefault("history", []).append(history_entry)
                return dict(flag)

        new_flag = {
            "key": normalized_key,
            "scope": scope_norm,
            "enabled": bool(enabled),
            "description": description.strip() if description else None,
            "org_id": org_id,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
            "updated_by": actor,
            "history": [history_entry],
        }
        flags.append(new_flag)
        store["feature_flags"] = flags
        return dict(new_flag)


def delete_feature_flag(
    *,
    key: str,
    scope: str,
    org_id: Optional[int],
    user_id: Optional[int],
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
    status: Optional[str],
    severity: Optional[str],
    tag: Optional[str],
    limit: int,
    offset: int,
) -> Tuple[List[Dict[str, Any]], int]:
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
    return incidents[safe_offset:safe_offset + safe_limit], total


def create_incident(
    *,
    title: str,
    status: Optional[str],
    severity: Optional[str],
    summary: Optional[str],
    tags: Optional[List[str]],
    actor: Optional[str],
) -> Dict[str, Any]:
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
        "created_by": actor,
        "updated_by": actor,
        "timeline": [timeline_entry],
    }
    with _locked_store(write=True) as store:
        store.setdefault("incidents", []).append(incident)
    return dict(incident)


def update_incident(
    *,
    incident_id: str,
    title: Optional[str],
    status: Optional[str],
    severity: Optional[str],
    summary: Optional[str],
    tags: Optional[List[str]],
    update_message: Optional[str],
    actor: Optional[str],
) -> Dict[str, Any]:
    now = _now_iso()
    with _locked_store(write=True) as store:
        incidents = store.get("incidents", [])
        for incident in incidents:
            if incident.get("id") != incident_id:
                continue
            if title is not None:
                incident["title"] = title.strip() or incident.get("title")
            if status is not None:
                status_norm = status.strip().lower()
                if status_norm not in _INCIDENT_STATUSES:
                    raise ValueError("invalid_status")
                incident["status"] = status_norm
                incident["resolved_at"] = now if status_norm == "resolved" else None
            if severity is not None:
                severity_norm = severity.strip().lower()
                if severity_norm not in _INCIDENT_SEVERITIES:
                    raise ValueError("invalid_severity")
                incident["severity"] = severity_norm
            if summary is not None:
                incident["summary"] = summary.strip() or None
            if tags is not None:
                incident["tags"] = tags
            if update_message:
                incident.setdefault("timeline", []).append(
                    {
                        "id": f"evt_{uuid4().hex[:10]}",
                        "message": update_message.strip(),
                        "created_at": now,
                        "actor": actor,
                    }
                )
            incident["updated_at"] = now
            incident["updated_by"] = actor
            return dict(incident)
    raise ValueError("not_found")


def add_incident_event(
    *,
    incident_id: str,
    message: str,
    actor: Optional[str],
) -> Dict[str, Any]:
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
            return dict(incident)
    raise ValueError("not_found")


def delete_incident(*, incident_id: str) -> None:
    with _locked_store(write=True) as store:
        incidents = store.get("incidents", [])
        remaining = [item for item in incidents if item.get("id") != incident_id]
        if len(remaining) == len(incidents):
            raise ValueError("not_found")
        store["incidents"] = remaining
