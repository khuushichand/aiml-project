# admin_bundle_service.py
# Description: Service layer for admin backup bundle operations.
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import shutil
import sqlite3
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.exceptions import (
    BundleConcurrencyError,
    BundleDiskSpaceError,
    BundleExportError,
    BundleImportError,
    BundleNotFoundError,
    BundleRateLimitError,
    BundleSchemaIncompatibleError,
)
from tldw_Server_API.app.services.admin_data_ops_service import (
    _backup_base_dir,
    _resolve_dataset_db_path,
    _validate_backup_dataset,
    create_backup_snapshot,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MANIFEST_VERSION = 1
_ALL_DATASETS = ("media", "chacha", "prompts", "evaluations", "audit", "authnz")
_PER_USER_DATASETS = frozenset(_ALL_DATASETS) - {"authnz"}

# Concurrency: only one bundle operation at a time
_bundle_lock = asyncio.Lock()

# Rate limiting: 5 operations per hour per (user_id, op_type)
_rate_limit_windows: dict[tuple[int, str], list[float]] = {}
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW_SECONDS = 3600


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BundleMetadata:
    bundle_id: str
    user_id: int | None
    created_at: datetime
    size_bytes: int
    datasets: list[str]
    schema_versions: dict[str, int | None]
    app_version: str | None
    manifest_version: int
    notes: str | None


# ---------------------------------------------------------------------------
# Schema version registry
# ---------------------------------------------------------------------------
def _get_schema_versions() -> dict[str, int | None]:
    """Collect current schema versions from DB modules (lazy imports)."""
    versions: dict[str, int | None] = {}
    try:
        from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
        versions["media"] = int(MediaDatabase._CURRENT_SCHEMA_VERSION)
    except Exception:
        versions["media"] = None
    try:
        from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
        versions["chacha"] = int(CharactersRAGDB._CURRENT_SCHEMA_VERSION)
    except Exception:
        versions["chacha"] = None
    try:
        from tldw_Server_API.app.core.DB_Management.Prompts_DB import PromptsDatabase
        versions["prompts"] = int(PromptsDatabase._CURRENT_SCHEMA_VERSION)
    except Exception:
        versions["prompts"] = None
    # Evaluations, audit, authnz may not expose a version constant
    for name in ("evaluations", "audit", "authnz"):
        versions.setdefault(name, None)
    return versions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _bundle_base_dir() -> str:
    base = _backup_base_dir()
    return os.path.join(base, "bundles")


def _check_rate_limit(user_id: int, op_type: str) -> None:
    key = (user_id, op_type)
    now = time.monotonic()
    window = _rate_limit_windows.get(key, [])
    # Prune old entries
    window = [t for t in window if now - t < _RATE_LIMIT_WINDOW_SECONDS]
    if len(window) >= _RATE_LIMIT_MAX:
        oldest = min(window)
        retry_after = int(_RATE_LIMIT_WINDOW_SECONDS - (now - oldest)) + 1
        exc = BundleRateLimitError("rate_limit_exceeded")
        exc.retry_after = retry_after  # type: ignore[attr-defined]
        raise exc
    window.append(now)
    _rate_limit_windows[key] = window


def _check_disk_space(path: str, required_bytes: int) -> None:
    os.makedirs(path, exist_ok=True)
    usage = shutil.disk_usage(path)
    if usage.free < required_bytes:
        raise BundleDiskSpaceError("insufficient_disk_space")


def _compute_sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _get_app_version() -> str | None:
    try:
        from importlib.metadata import version
        return version("tldw_Server_API")
    except Exception:
        pass
    try:
        import tomllib
        pyproject = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
            "pyproject.toml",
        )
        if os.path.isfile(pyproject):
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            return data.get("project", {}).get("version")
    except Exception:
        pass
    return None


def _estimate_total_db_size(datasets: list[str], user_id: int | None) -> int:
    total = 0
    for ds in datasets:
        try:
            db_path, _ = _resolve_dataset_db_path(ds, user_id)
            if os.path.isfile(db_path):
                total += os.path.getsize(db_path)
        except Exception:
            pass
    return max(total, 1024)  # at least 1 KB estimate


def _build_manifest(
    *,
    user_id: int | None,
    datasets: list[str],
    files: dict[str, dict[str, str]],
    schema_versions: dict[str, int | None],
    notes: str | None,
) -> dict[str, Any]:
    return {
        "manifest_version": _MANIFEST_VERSION,
        "app_version": _get_app_version(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "datasets": datasets,
        "files": files,
        "schema_versions": schema_versions,
        "notes": notes,
        "platform": {
            "os": platform.system(),
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
        },
    }


def _validate_bundle_id(bundle_id: str) -> str:
    """Sanitize bundle_id to prevent path traversal."""
    name = os.path.basename(str(bundle_id or "").strip())
    if not name or name != bundle_id or name.startswith("-"):
        raise BundleNotFoundError("bundle_not_found")
    if not name.endswith(".zip"):
        raise BundleNotFoundError("bundle_not_found")
    return name


def _resolve_bundle_path(bundle_id: str) -> str:
    name = _validate_bundle_id(bundle_id)
    path = os.path.join(_bundle_base_dir(), name)
    if not os.path.isfile(path):
        raise BundleNotFoundError("bundle_not_found")
    return path


def _read_manifest_from_zip(zip_path: str) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path, "r") as zf:
        if "manifest.json" not in zf.namelist():
            raise BundleImportError("missing_manifest")
        with zf.open("manifest.json") as mf:
            return json.loads(mf.read())


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------
def create_bundle(
    *,
    datasets: list[str] | None,
    user_id: int | None,
    include_vector_store: bool = False,
    notes: str | None = None,
    max_backups: int | None = None,
    admin_user_id: int = 0,
) -> BundleMetadata:
    """Create a backup bundle ZIP containing snapshots of the requested datasets."""
    if include_vector_store:
        raise BundleExportError("vector_store_export_not_supported")

    effective_datasets = list(datasets) if datasets else list(_ALL_DATASETS)

    # Validate each dataset name
    for ds in effective_datasets:
        _validate_backup_dataset(ds)

    # Validate user_id requirement
    per_user_requested = [ds for ds in effective_datasets if ds in _PER_USER_DATASETS]
    if per_user_requested and user_id is None:
        # Auto-resolve in single-user mode
        try:
            user_id = DatabasePaths.get_single_user_id()
        except Exception as exc:
            raise BundleExportError("user_id_required") from exc

    # Rate limit
    _check_rate_limit(admin_user_id, "export")

    # Estimate size and check disk space
    estimated = _estimate_total_db_size(effective_datasets, user_id)
    dest_dir = _bundle_base_dir()
    _check_disk_space(dest_dir, estimated * 2)

    staging_dir = tempfile.mkdtemp(prefix="tldw_bundle_")
    try:
        files_meta: dict[str, dict[str, str]] = {}

        for ds in effective_datasets:
            ds_user_id = None if ds == "authnz" else user_id
            try:
                backup_file = create_backup_snapshot(
                    dataset=ds,
                    user_id=ds_user_id,
                    backup_type="full",
                    max_backups=max_backups,
                )
            except Exception as exc:
                raise BundleExportError(
                    f"backup_failed:{ds}: {exc}"
                ) from exc

            # Copy to staging dir
            dest = os.path.join(staging_dir, backup_file.filename)
            shutil.copy2(backup_file.path, dest)

            sha256 = _compute_sha256(dest)
            files_meta[backup_file.filename] = {
                "dataset": ds,
                "sha256": sha256,
                "hash_algorithm": "sha256",
                "size_bytes": str(backup_file.size_bytes),
            }

        schema_versions = _get_schema_versions()
        manifest = _build_manifest(
            user_id=user_id,
            datasets=effective_datasets,
            files=files_meta,
            schema_versions=schema_versions,
            notes=notes,
        )

        manifest_path = os.path.join(staging_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Build ZIP filename
        user_label = str(user_id) if user_id else "global"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        zip_name = f"tldw-backup-bundle-{user_label}-{timestamp}.zip"
        zip_path = os.path.join(staging_dir, zip_name)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(manifest_path, "manifest.json")
            for filename in files_meta:
                zf.write(os.path.join(staging_dir, filename), filename)

        # Move to final location
        os.makedirs(dest_dir, exist_ok=True)
        final_path = os.path.join(dest_dir, zip_name)
        shutil.move(zip_path, final_path)

        stat = os.stat(final_path)
        return BundleMetadata(
            bundle_id=zip_name,
            user_id=user_id,
            created_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            size_bytes=int(stat.st_size),
            datasets=effective_datasets,
            schema_versions=schema_versions,
            app_version=manifest.get("app_version"),
            manifest_version=_MANIFEST_VERSION,
            notes=notes,
        )
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


async def create_bundle_async(
    *,
    datasets: list[str] | None,
    user_id: int | None,
    include_vector_store: bool = False,
    notes: str | None = None,
    max_backups: int | None = None,
    admin_user_id: int = 0,
) -> BundleMetadata:
    """Async wrapper that acquires the concurrency lock, then runs create_bundle in a thread."""
    if _bundle_lock.locked():
        raise BundleConcurrencyError("bundle_operation_in_progress")
    async with _bundle_lock:
        return await asyncio.to_thread(
            create_bundle,
            datasets=datasets,
            user_id=user_id,
            include_vector_store=include_vector_store,
            notes=notes,
            max_backups=max_backups,
            admin_user_id=admin_user_id,
        )


def list_bundles(
    *,
    user_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[BundleMetadata], int]:
    """List available bundles, optionally filtered by user_id."""
    base = _bundle_base_dir()
    if not os.path.isdir(base):
        return [], 0

    items: list[BundleMetadata] = []
    for entry in os.scandir(base):
        if not entry.is_file() or not entry.name.endswith(".zip"):
            continue
        try:
            manifest = _read_manifest_from_zip(entry.path)
        except Exception:
            logger.warning("Skipping unreadable bundle: {}", entry.name)
            continue

        bundle_user_id = manifest.get("user_id")
        if user_id is not None and bundle_user_id != user_id:
            continue

        stat = entry.stat()
        items.append(BundleMetadata(
            bundle_id=entry.name,
            user_id=bundle_user_id,
            created_at=datetime.fromisoformat(manifest["created_at"]) if manifest.get("created_at") else datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            size_bytes=int(stat.st_size),
            datasets=manifest.get("datasets", []),
            schema_versions=manifest.get("schema_versions", {}),
            app_version=manifest.get("app_version"),
            manifest_version=manifest.get("manifest_version", 0),
            notes=manifest.get("notes"),
        ))

    items.sort(key=lambda m: m.created_at, reverse=True)
    total = len(items)
    return items[offset:offset + limit], total


def get_bundle_metadata(bundle_id: str) -> BundleMetadata:
    """Get metadata for a single bundle."""
    path = _resolve_bundle_path(bundle_id)
    manifest = _read_manifest_from_zip(path)
    stat = os.stat(path)
    return BundleMetadata(
        bundle_id=bundle_id,
        user_id=manifest.get("user_id"),
        created_at=datetime.fromisoformat(manifest["created_at"]) if manifest.get("created_at") else datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        size_bytes=int(stat.st_size),
        datasets=manifest.get("datasets", []),
        schema_versions=manifest.get("schema_versions", {}),
        app_version=manifest.get("app_version"),
        manifest_version=manifest.get("manifest_version", 0),
        notes=manifest.get("notes"),
    )


def get_bundle_path(bundle_id: str) -> str:
    """Resolve and return the filesystem path for a bundle."""
    return _resolve_bundle_path(bundle_id)


def delete_bundle(bundle_id: str) -> None:
    """Delete a bundle ZIP from disk."""
    path = _resolve_bundle_path(bundle_id)
    os.remove(path)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------
def import_bundle(
    *,
    file_path: str,
    user_id: int | None,
    dry_run: bool = False,
    allow_downgrade: bool = False,
    admin_user_id: int = 0,
) -> dict[str, Any]:
    """Import a bundle ZIP, restoring datasets.

    Returns a dict compatible with BundleImportResponse.
    """
    _check_rate_limit(admin_user_id, "import")

    if not os.path.isfile(file_path):
        raise BundleImportError("file_not_found")

    # Check disk space (3x ZIP size)
    zip_size = os.path.getsize(file_path)
    _check_disk_space(
        os.path.dirname(file_path) or _bundle_base_dir(),
        zip_size * 3,
    )

    try:
        manifest = _read_manifest_from_zip(file_path)
    except Exception as exc:
        raise BundleImportError(f"invalid_bundle: {exc}") from exc

    m_version = manifest.get("manifest_version", 0)
    if m_version > _MANIFEST_VERSION:
        raise BundleImportError("unsupported_manifest_version")

    current_versions = _get_schema_versions()
    manifest_versions = manifest.get("schema_versions", {})
    datasets = manifest.get("datasets", [])
    files_meta = manifest.get("files", {})

    # Per-user datasets need a user_id
    per_user_in_bundle = [ds for ds in datasets if ds in _PER_USER_DATASETS]
    if per_user_in_bundle and user_id is None:
        try:
            user_id = DatabasePaths.get_single_user_id()
        except Exception as exc:
            raise BundleImportError("user_id_required") from exc

    warnings: list[str] = []
    validations: list[dict[str, Any]] = []

    # App version check
    app_version = _get_app_version()
    manifest_app_version = manifest.get("app_version")
    if manifest_app_version and app_version:
        m_major = manifest_app_version.split(".")[0] if manifest_app_version else ""
        c_major = app_version.split(".")[0] if app_version else ""
        if m_major != c_major:
            warnings.append(
                f"Major version mismatch: bundle={manifest_app_version}, current={app_version}"
            )

    # Schema compatibility checks
    for ds in datasets:
        m_ver = manifest_versions.get(ds)
        c_ver = current_versions.get(ds)
        validation: dict[str, Any] = {
            "dataset": ds,
            "manifest_version": m_ver,
            "current_version": c_ver,
            "compatible": True,
            "message": "ok",
        }
        if m_ver is not None and c_ver is not None:
            if m_ver > c_ver and not allow_downgrade:
                validation["compatible"] = False
                validation["message"] = (
                    f"Schema version {m_ver} is newer than current {c_ver}"
                )
        validations.append(validation)

    incompatible = [v for v in validations if not v["compatible"]]
    if incompatible:
        if dry_run:
            return {
                "status": "incompatible",
                "datasets_restored": [],
                "warnings": warnings,
                "safety_snapshots": {},
                "validations": validations,
            }
        raise BundleSchemaIncompatibleError(
            f"schema_incompatible: {', '.join(v['dataset'] for v in incompatible)}"
        )

    # Verify checksums
    with zipfile.ZipFile(file_path, "r") as zf:
        for filename, meta in files_meta.items():
            if filename not in zf.namelist():
                raise BundleImportError(f"missing_file_in_bundle: {filename}")
            # Extract to temp and verify
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(zf.read(filename))
                tmp_path = tmp.name
            try:
                actual_size = os.path.getsize(tmp_path)
                expected_size = meta.get("size_bytes")
                if expected_size is not None and actual_size != int(expected_size):
                    raise BundleImportError(
                        f"size_verification_failed: {filename} "
                        f"(expected {expected_size}, got {actual_size})"
                    )
                actual_hash = _compute_sha256(tmp_path)
                expected_hash = meta.get("sha256", "")
                if actual_hash != expected_hash:
                    raise BundleImportError(
                        f"checksum_verification_failed: {filename}"
                    )
            finally:
                os.unlink(tmp_path)

    if dry_run:
        return {
            "status": "compatible",
            "datasets_restored": [],
            "warnings": warnings,
            "safety_snapshots": {},
            "validations": validations,
        }

    # Real import
    staging_dir = tempfile.mkdtemp(prefix="tldw_bundle_import_")
    safety_snapshots: dict[str, str] = {}
    datasets_restored: list[str] = []

    try:
        # Extract files with path traversal protection
        with zipfile.ZipFile(file_path, "r") as zf:
            for member in zf.infolist():
                # Reject any member whose resolved path escapes staging_dir
                target = os.path.realpath(
                    os.path.join(staging_dir, member.filename)
                )
                if not target.startswith(os.path.realpath(staging_dir) + os.sep) and target != os.path.realpath(staging_dir):
                    raise BundleImportError(
                        f"path_traversal_detected: {member.filename}"
                    )
                zf.extract(member, staging_dir)

        for ds in datasets:
            ds_user_id = None if ds == "authnz" else user_id

            # Create safety snapshot before overwriting
            try:
                safety = create_backup_snapshot(
                    dataset=ds,
                    user_id=ds_user_id,
                    backup_type="full",
                    max_backups=None,
                )
                safety_snapshots[ds] = safety.filename
            except Exception as exc:
                logger.warning("Safety snapshot failed for {}: {}", ds, exc)

            # Find the matching file in the bundle
            ds_filename = None
            for filename, meta in files_meta.items():
                if meta.get("dataset") == ds:
                    ds_filename = filename
                    break

            if ds_filename is None:
                warnings.append(f"No file found in bundle for dataset '{ds}'")
                continue

            # Resolve live DB path and copy
            try:
                live_db_path, _ = _resolve_dataset_db_path(ds, ds_user_id)
                extracted_path = os.path.join(staging_dir, ds_filename)
                if not os.path.isfile(extracted_path):
                    warnings.append(f"Extracted file missing for dataset '{ds}'")
                    continue
                os.makedirs(os.path.dirname(live_db_path), exist_ok=True)
                shutil.copy2(extracted_path, live_db_path)
                datasets_restored.append(ds)
            except Exception as exc:
                logger.error("Failed to restore dataset {}: {}", ds, exc)
                # Rollback already-restored datasets
                for restored_ds in datasets_restored:
                    snap_id = safety_snapshots.get(restored_ds)
                    if snap_id:
                        try:
                            from tldw_Server_API.app.services.admin_data_ops_service import (
                                restore_backup_snapshot,
                            )
                            r_user_id = None if restored_ds == "authnz" else user_id
                            restore_backup_snapshot(
                                dataset=restored_ds,
                                user_id=r_user_id,
                                backup_id=snap_id,
                            )
                        except Exception as rollback_exc:
                            logger.error(
                                "Rollback failed for {}: {}", restored_ds, rollback_exc
                            )
                raise BundleImportError(
                    f"restore_failed:{ds}: {exc}"
                ) from exc

        return {
            "status": "imported",
            "datasets_restored": datasets_restored,
            "warnings": warnings,
            "safety_snapshots": safety_snapshots,
            "validations": validations,
        }
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


async def import_bundle_async(
    *,
    file_path: str,
    user_id: int | None,
    dry_run: bool = False,
    allow_downgrade: bool = False,
    admin_user_id: int = 0,
) -> dict[str, Any]:
    """Async wrapper that acquires the concurrency lock, then runs import_bundle in a thread."""
    if _bundle_lock.locked():
        raise BundleConcurrencyError("bundle_operation_in_progress")
    async with _bundle_lock:
        return await asyncio.to_thread(
            import_bundle,
            file_path=file_path,
            user_id=user_id,
            dry_run=dry_run,
            allow_downgrade=allow_downgrade,
            admin_user_id=admin_user_id,
        )
