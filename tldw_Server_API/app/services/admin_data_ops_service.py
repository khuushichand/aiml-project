# admin_data_ops_service.py
# Description: Admin data operations helpers (backups, retention policies, exports)
from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.retention_policies import (
    RETENTION_POLICIES,
    apply_retention_overrides,
    upsert_retention_override,
)
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.DB_Backups import (
    create_backup,
    create_incremental_backup,
    create_postgres_backup,
    restore_postgres_backup,
    restore_single_db_backup,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.exceptions import (
    InvalidBackupIdError,
    InvalidBackupPathError,
    InvalidBackupUserIdError,
    InvalidRetentionPolicyError,
    InvalidRetentionRangeError,
    UnknownBackupDatasetError,
)
from tldw_Server_API.app.core.Utils.path_utils import safe_join
from tldw_Server_API.app.core.Utils.Utils import get_project_relative_path


@dataclass(frozen=True)
class BackupFile:
    dataset: str
    user_id: int | None
    filename: str
    path: str
    size_bytes: int
    created_at: datetime


DATASET_DB_RESOLVERS = {
    "media": DatabasePaths.get_media_db_path,
    "chacha": DatabasePaths.get_chacha_db_path,
    "prompts": DatabasePaths.get_prompts_db_path,
    "evaluations": DatabasePaths.get_evaluations_db_path,
    "audit": DatabasePaths.get_audit_db_path,
}
_BACKUP_DATASETS = frozenset([*DATASET_DB_RESOLVERS.keys(), "authnz"])
_BACKUP_EXTENSIONS = (".db", ".sqlib", ".dump")


def _backup_base_dir() -> str:
    return os.environ.get("TLDW_DB_BACKUP_PATH") or get_project_relative_path("tldw_DB_Backups")


def _validate_backup_dataset(dataset: str) -> str:
    name = str(dataset or "").strip().lower()
    if name not in _BACKUP_DATASETS:
        raise UnknownBackupDatasetError("unknown_dataset")
    return name


def _normalize_user_id(user_id: int | None) -> int | None:
    if user_id is None:
        return None
    try:
        value = int(user_id)
    except (TypeError, ValueError) as exc:
        raise InvalidBackupUserIdError("invalid_user_id") from exc
    if value <= 0:
        raise InvalidBackupUserIdError("invalid_user_id")
    return value


def _backup_path_error(_: Exception | None) -> InvalidBackupPathError:
    return InvalidBackupPathError("invalid_backup_path")


def _safe_join(base_dir: str, name: str) -> str:
    resolved = safe_join(base_dir, name, error_factory=_backup_path_error)
    if resolved is None:
        raise InvalidBackupPathError("invalid_backup_path")
    return resolved


def _backup_dir_for_dataset(dataset: str, user_id: int | None) -> str:
    base_dir = _backup_base_dir()
    dataset_name = _validate_backup_dataset(dataset)
    safe_user_id = _normalize_user_id(user_id)
    if safe_user_id is not None:
        base_dir = _safe_join(base_dir, f"user_{safe_user_id}")
    return _safe_join(base_dir, dataset_name)


def _extract_backup_path(message: str) -> str | None:
    if not message:
        return None
    for prefix in ("Backup created: ", "Incremental backup created: "):
        if message.startswith(prefix):
            return message[len(prefix):].strip()
    return None


def _list_backup_files(dataset: str, user_id: int | None) -> list[BackupFile]:
    backup_dir = _backup_dir_for_dataset(dataset, user_id)
    if not os.path.isdir(backup_dir):
        return []
    files = []
    for entry in os.scandir(backup_dir):
        if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
            continue
        if not entry.name.endswith(_BACKUP_EXTENSIONS):
            continue
        stat = entry.stat()
        files.append(
            BackupFile(
                dataset=dataset,
                user_id=user_id,
                filename=entry.name,
                path=entry.path,
                size_bytes=int(stat.st_size),
                created_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            )
        )
    files.sort(key=lambda item: item.created_at, reverse=True)
    return files


def list_backup_items(
    *,
    dataset: str | None,
    user_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[BackupFile], int]:
    datasets = [_validate_backup_dataset(dataset)] if dataset is not None else [*DATASET_DB_RESOLVERS.keys(), "authnz"]
    items: list[BackupFile] = []
    for key in datasets:
        dataset_user_id = None if key == "authnz" else user_id
        items.extend(_list_backup_files(key, dataset_user_id))
    items.sort(key=lambda item: item.created_at, reverse=True)
    total = len(items)
    return items[offset: offset + limit], total


def _resolve_dataset_db_path(dataset: str, user_id: int | None) -> tuple[str, int | None]:
    dataset_name = _validate_backup_dataset(dataset)
    if dataset_name == "authnz":
        settings = get_settings()
        url = settings.DATABASE_URL
        parsed = urlparse(url)
        scheme = (parsed.scheme or "").lower()
        if scheme.startswith("sqlite") or scheme.startswith("file") or not scheme:
            fs_path = parsed.path or url
            if fs_path.startswith("//"):
                fs_path = fs_path[1:]
            fs_path = fs_path or url
            return fs_path, None
        return url, None

    resolver = DATASET_DB_RESOLVERS.get(dataset_name)
    effective_user_id = user_id if user_id is not None else DatabasePaths.get_single_user_id()
    return str(resolver(effective_user_id)), effective_user_id


def _config_from_postgres_url(url: str) -> DatabaseConfig:
    parsed = urlparse(url)
    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        connection_string=url,
        pg_host=parsed.hostname or "localhost",
        pg_port=int(parsed.port or 5432),
        pg_database=(parsed.path or "/").lstrip("/") or None,
        pg_user=parsed.username or None,
        pg_password=parsed.password or None,
        pg_sslmode="prefer",
    )


def _normalize_backup_filename(path: str) -> str:
    return os.path.basename(path)


def _validate_backup_id(backup_id: str) -> str:
    name = os.path.basename(str(backup_id or "").strip())
    if not name:
        raise InvalidBackupIdError("invalid_backup_id")
    if name != backup_id:
        raise InvalidBackupIdError("invalid_backup_id")
    if name.startswith("-"):
        raise InvalidBackupIdError("invalid_backup_id")
    if not name.endswith(_BACKUP_EXTENSIONS):
        raise InvalidBackupIdError("invalid_backup_id")
    return name


def _prune_backups(backup_dir: str, max_backups: int) -> int:
    if max_backups <= 0:
        return 0
    if not os.path.isdir(backup_dir):
        return 0
    files = [
        entry
        for entry in os.scandir(backup_dir)
        if entry.is_file(follow_symlinks=False)
        and not entry.is_symlink()
        and entry.name.endswith(_BACKUP_EXTENSIONS)
    ]
    files.sort(key=lambda entry: entry.stat().st_mtime, reverse=True)
    removed = 0
    for entry in files[max_backups:]:
        try:
            os.remove(entry.path)
            removed += 1
        except Exception as exc:
            logger.warning(f"Failed to prune backup {entry.path}: {exc}")
    return removed


def create_backup_snapshot(
    *,
    dataset: str,
    user_id: int | None,
    backup_type: str,
    max_backups: int | None,
) -> BackupFile:
    db_path, effective_user_id = _resolve_dataset_db_path(dataset, user_id)
    backup_dir = _backup_dir_for_dataset(dataset, effective_user_id)
    os.makedirs(backup_dir, exist_ok=True)

    if dataset == "authnz" and not str(db_path).startswith("sqlite") and str(db_path).startswith("postgres"):
        config = _config_from_postgres_url(db_path)
        backend = SimpleNamespace(backend_type=BackendType.POSTGRESQL, config=config)
        backup_path = create_postgres_backup(backend, backup_dir, label="authnz")
        if not backup_path or not os.path.exists(backup_path):
            raise RuntimeError(backup_path or "pg_dump failed")
        filename = _normalize_backup_filename(backup_path)
    else:
        if backup_type == "incremental":
            message = create_incremental_backup(db_path, backup_dir, dataset)
        else:
            message = create_backup(db_path, backup_dir, dataset)
        backup_path = _extract_backup_path(message)
        if not backup_path or not os.path.exists(backup_path):
            raise RuntimeError(message or "Backup failed")
        filename = _normalize_backup_filename(backup_path)

    if max_backups is not None:
        _prune_backups(backup_dir, max_backups)

    stat = os.stat(os.path.join(backup_dir, filename))
    return BackupFile(
        dataset=dataset,
        user_id=effective_user_id,
        filename=filename,
        path=os.path.join(backup_dir, filename),
        size_bytes=int(stat.st_size),
        created_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
    )


def restore_backup_snapshot(
    *,
    dataset: str,
    user_id: int | None,
    backup_id: str,
) -> str:
    db_path, effective_user_id = _resolve_dataset_db_path(dataset, user_id)
    backup_dir = _backup_dir_for_dataset(dataset, effective_user_id)
    backup_name = _validate_backup_id(backup_id)

    if dataset == "authnz" and not str(db_path).startswith("sqlite") and str(db_path).startswith("postgres"):
        config = _config_from_postgres_url(db_path)
        backend = SimpleNamespace(backend_type=BackendType.POSTGRESQL, config=config)
        backup_path = _safe_join(backup_dir, backup_name)
        result = restore_postgres_backup(backend, backup_path, drop_first=True)
        if result != "ok":
            raise RuntimeError(result)
        return "ok"

    result = restore_single_db_backup(db_path, backup_dir, dataset, backup_name)
    if not result.startswith("Database restored"):
        raise RuntimeError(result)
    return result



async def list_retention_policies() -> list[dict[str, Any]]:
    settings = get_settings()
    await apply_retention_overrides(settings)
    policies = []
    for key, meta in RETENTION_POLICIES.items():
        attr = meta["attr"]
        value = getattr(settings, attr, None)
        policies.append({
            "key": key,
            "days": int(value) if value is not None else None,
            "description": meta.get("description"),
        })
    return policies


async def update_retention_policy(policy_key: str, days: int) -> dict[str, Any]:
    meta = RETENTION_POLICIES.get(policy_key)
    if not meta:
        raise InvalidRetentionPolicyError("unknown_policy")
    min_val = int(meta["min"])
    max_val = int(meta["max"])
    if days < min_val or days > max_val:
        raise InvalidRetentionRangeError("invalid_range")

    settings = get_settings()
    effective_days = int(days)
    if policy_key == "privilege_snapshots_weekly":
        try:
            primary = int(getattr(settings, RETENTION_POLICIES["privilege_snapshots"]["attr"]))
            if effective_days < primary:
                effective_days = primary
        except Exception:
            pass
    await upsert_retention_override(policy_key, effective_days)
    setattr(settings, meta["attr"], effective_days)

    return {
        "key": policy_key,
        "days": effective_days,
        "description": meta.get("description"),
    }


def _csv_text(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(list(headers))
    for row in rows:
        writer.writerow(list(row))
    return output.getvalue()


def build_audit_log_csv(entries: Iterable[Any]) -> str:
    headers = [
        "id",
        "user_id",
        "username",
        "action",
        "resource",
        "details",
        "ip_address",
        "created_at",
    ]
    rows = []
    for entry in entries:
        created_at = getattr(entry, "created_at", None)
        rows.append([
            getattr(entry, "id", None),
            getattr(entry, "user_id", None),
            getattr(entry, "username", None),
            getattr(entry, "action", None),
            getattr(entry, "resource", None),
            json.dumps(getattr(entry, "details", None)) if getattr(entry, "details", None) is not None else None,
            getattr(entry, "ip_address", None),
            created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        ])
    return _csv_text(headers, rows)


def build_audit_log_json(entries: Iterable[Any], *, total: int, limit: int, offset: int) -> str:
    payload = {
        "items": [
            entry.model_dump(mode="json") if hasattr(entry, "model_dump") else dict(entry)
            for entry in entries
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
    return json.dumps(payload, indent=2)


def build_users_csv(users: Iterable[dict[str, Any]]) -> str:
    headers = [
        "id",
        "uuid",
        "username",
        "email",
        "role",
        "is_active",
        "is_verified",
        "created_at",
        "last_login",
        "storage_quota_mb",
        "storage_used_mb",
    ]
    rows = []
    for user in users:
        created_at = user.get("created_at")
        last_login = user.get("last_login")
        rows.append([
            user.get("id"),
            user.get("uuid"),
            user.get("username"),
            user.get("email"),
            user.get("role"),
            user.get("is_active"),
            user.get("is_verified"),
            created_at.isoformat() if isinstance(created_at, datetime) else created_at,
            last_login.isoformat() if isinstance(last_login, datetime) else last_login,
            user.get("storage_quota_mb"),
            user.get("storage_used_mb"),
        ])
    return _csv_text(headers, rows)


def build_users_json(users: Iterable[dict[str, Any]], *, total: int, limit: int, offset: int) -> str:
    normalized = []
    for user in users:
        payload = dict(user)
        for key in ("created_at", "last_login"):
            value = payload.get(key)
            if isinstance(value, datetime):
                payload[key] = value.isoformat()
        normalized.append(payload)
    return json.dumps({
        "items": normalized,
        "total": total,
        "limit": limit,
        "offset": offset,
    }, indent=2)
