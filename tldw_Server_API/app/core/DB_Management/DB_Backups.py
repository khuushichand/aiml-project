# Backup_Manager.py
#
# Imports:
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime
from typing import Dict, Optional

from loguru import logger

# Local Imports:
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Utils.Utils import get_project_relative_path
from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseBackend, BackendType
#
# End of Imports
#######################################################################################################################
#
# Functions:

def init_backup_directory(backup_base_dir: str, db_name: str) -> str:
    """Initialize backup directory for a specific database."""
    backup_dir = os.path.join(backup_base_dir, db_name)
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def create_backup(db_path: str, backup_dir: str, db_name: str) -> str:
    """Create a full backup of the database."""
    try:
        # Guard: in-memory databases cannot be backed up to disk
        mem = str(db_path).strip()
        if mem == ":memory:" or mem.startswith("file::memory:"):
            return "Cannot create backup for in-memory database"
        db_path = os.path.abspath(db_path)
        backup_dir = os.path.abspath(backup_dir)
        if not os.path.exists(db_path):
            error_msg = f"Database not found: {db_path}"
            logger.error(error_msg)
            return error_msg
        os.makedirs(backup_dir, exist_ok=True)

        logger.info("Creating backup:")
        logger.info(f"  DB Path: {db_path}")
        logger.info(f"  Backup Dir: {backup_dir}")
        logger.info(f"  DB Name: {db_name}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"{db_name}_backup_{timestamp}.db")
        logger.info(f"  Full backup path: {backup_file}")

        # Create a backup using SQLite's backup API
        with sqlite3.connect(db_path) as source, \
                sqlite3.connect(backup_file) as target:
            source.backup(target)

        # Copy associated WAL/SHM files when present to keep the journal consistent.
        for suffix in ("-wal", "-shm"):
            sidecar = f"{db_path}{suffix}"
            if os.path.exists(sidecar):
                backup_sidecar = f"{backup_file}{suffix}"
                shutil.copy2(sidecar, backup_sidecar)
                logger.info(f"Copied journal file: {backup_sidecar}")

        logger.info(f"Backup created successfully: {backup_file}")
        return f"Backup created: {backup_file}"
    except Exception as e:
        error_msg = f"Failed to create backup: {str(e)}"
        logger.error(error_msg)
        return error_msg


def create_incremental_backup(db_path: str, backup_dir: str, db_name: str) -> str:
    """Create an incremental backup using VACUUM INTO."""
    try:
        mem = str(db_path).strip()
        if mem == ":memory:" or mem.startswith("file::memory:"):
            return "Cannot create incremental backup for in-memory database"
        db_path = os.path.abspath(db_path)
        backup_dir = os.path.abspath(backup_dir)
        if not os.path.exists(db_path):
            error_msg = f"Database not found: {db_path}"
            logger.error(error_msg)
            return error_msg
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir,
                                   f"{db_name}_incremental_{timestamp}.sqlib")

        with sqlite3.connect(db_path) as conn:
            try:
                conn.execute("VACUUM INTO ?", (backup_file,))
            except sqlite3.OperationalError:
                escaped_path = backup_file.replace("'", "''")
                conn.execute(f"VACUUM INTO '{escaped_path}'")

        logger.info(f"Incremental backup created: {backup_file}")
        return f"Incremental backup created: {backup_file}"
    except Exception as e:
        error_msg = f"Failed to create incremental backup: {str(e)}"
        logger.error(error_msg)
        return error_msg


def list_backups(backup_dir: str) -> str:
    """List all available backups."""
    try:
        backups = [f for f in os.listdir(backup_dir)
                   if f.endswith(('.db', '.sqlib'))]
        backups.sort(reverse=True)  # Most recent first
        return "\n".join(backups) if backups else "No backups found"
    except Exception as e:
        error_msg = f"Failed to list backups: {str(e)}"
        logger.error(error_msg)
        return error_msg


def restore_single_db_backup(db_path: str, backup_dir: str, db_name: str, backup_name: str) -> str:
    """Restore database from a backup file."""
    try:
        logger.info(f"Restoring backup: {backup_name}")
        backup_path = os.path.join(backup_dir, backup_name)
        if not os.path.exists(backup_path):
            logger.error(f"Backup file not found: {backup_name}")
            return f"Backup file not found: {backup_name}"

        parent_dir = os.path.dirname(db_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        if os.path.exists(db_path):
            # Create a timestamp for the current db
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            current_backup = os.path.join(
                backup_dir, f"{db_name}_pre_restore_{timestamp}.db"
            )

            # Backup current database before restore
            logger.info(f"Creating backup of current database: {current_backup}")
            shutil.copy2(db_path, current_backup)
            for suffix in ("-wal", "-shm"):
                existing_sidecar = f"{db_path}{suffix}"
                backup_sidecar = f"{current_backup}{suffix}"
                if os.path.exists(existing_sidecar):
                    shutil.copy2(existing_sidecar, backup_sidecar)
                    logger.info(f"Saved journal snapshot: {backup_sidecar}")
        else:
            logger.info(
                f"No existing database at {db_path}; skipping pre-restore snapshot."
            )

        # Restore the backup
        logger.info(f"Restoring database from {backup_name}")
        shutil.copy2(backup_path, db_path)
        for suffix in ("-wal", "-shm"):
            backup_sidecar = f"{backup_path}{suffix}"
            target_sidecar = f"{db_path}{suffix}"
            if os.path.exists(backup_sidecar):
                shutil.copy2(backup_sidecar, target_sidecar)
                logger.info(f"Restored journal file: {target_sidecar}")
            elif os.path.exists(target_sidecar):
                # Remove stale sidecar files that do not exist for the backup snapshot.
                os.remove(target_sidecar)
                logger.info(f"Removed stale journal file: {target_sidecar}")

        logger.info(f"Database restored from {backup_name}")
        return f"Database restored from {backup_name}"
    except Exception as e:
        error_msg = f"Failed to restore backup: {str(e)}"
        logger.error(error_msg)
        return error_msg

def setup_backup_config(user_id: Optional[int] = None) -> Dict[str, Dict[str, str]]:
    """Setup configuration for database backups using centralized path utils.

    Returns a mapping of logical database names to their backup configuration.
    """
    # Standardized backup directory selection:
    # 1) TLDW_DB_BACKUP_PATH env var
    # 2) project-relative default ./tldw_DB_Backups/
    env_base = os.environ.get('TLDW_DB_BACKUP_PATH')
    backup_base_dir = env_base or get_project_relative_path('tldw_DB_Backups')
    os.makedirs(backup_base_dir, exist_ok=True)
    logger.info(f"Base backup directory: {os.path.abspath(backup_base_dir)}")

    uid = user_id if user_id is not None else DatabasePaths.get_single_user_id()

    # Resolve database paths
    db_paths = {
        'media': str(DatabasePaths.get_media_db_path(uid)),
        'chacha': str(DatabasePaths.get_chacha_db_path(uid)),
        'prompts': str(DatabasePaths.get_prompts_db_path(uid)),
        'evaluations': str(DatabasePaths.get_evaluations_db_path(uid)),
        'audit': str(DatabasePaths.get_audit_db_path(uid)),
    }

    configs: Dict[str, Dict[str, str]] = {}
    for name, path in db_paths.items():
        subdir = os.path.join(backup_base_dir, name)
        os.makedirs(subdir, exist_ok=True)
        logger.info(f"{name.capitalize()} backup directory: {os.path.abspath(subdir)}")
        configs[name] = {
            'db_path': path,
            'backup_dir': subdir,
            'db_name': name,
        }

    return configs


def _pg_dump_path() -> Optional[str]:
    """Return path to pg_dump binary if available, otherwise None."""
    path = shutil.which("pg_dump")
    if not path:
        logger.error("pg_dump not found on PATH. Install PostgreSQL client tools to enable backups.")
        return None
    return path


def create_postgres_backup(
    backend: DatabaseBackend,
    backup_dir: str,
    *,
    label: str = "content",
) -> str:
    """Create a PostgreSQL backup using pg_dump.

    Args:
        backend: A DatabaseBackend configured for PostgreSQL
        backup_dir: Target directory for the backup artifact
        label: Logical label to include in the backup filename

    Returns:
        str: Path to the backup file on success, or an error message on failure.
    """
    if backend.backend_type != BackendType.POSTGRESQL:
        msg = "create_postgres_backup requires a PostgreSQL backend"
        logger.error(msg)
        return msg

    pg_dump = _pg_dump_path()
    if not pg_dump:
        return "pg_dump not found on PATH"

    # Extract connection parameters from the backend configuration
    config = getattr(backend, "config", None)
    if not config:
        msg = "PostgreSQL backend missing configuration; cannot perform backup"
        logger.error(msg)
        return msg

    host = config.pg_host or "localhost"
    port = str(config.pg_port or 5432)
    dbname = config.pg_database or "tldw"
    user = config.pg_user or "postgres"
    password = config.pg_password or None

    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(backup_dir, f"{label}_pgdump_{timestamp}.dump")

    # Build pg_dump command
    cmd = [
        pg_dump,
        "-h", host,
        "-p", port,
        "-U", user,
        "-F", "c",            # custom format (compressed, pg_restore-compatible)
        "--no-owner",
        "--no-privileges",
        "-f", out_file,
        dbname,
    ]

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = str(password)

    try:
        logger.info(f"Running pg_dump → {out_file}")
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            logger.error(f"pg_dump failed ({proc.returncode}): {proc.stderr.strip()}")
            return f"pg_dump failed: {proc.stderr.strip()}"
        logger.info(f"PostgreSQL backup created: {out_file}")
        return out_file
    except FileNotFoundError:
        msg = "pg_dump executable not found; ensure PostgreSQL client tools are installed"
        logger.error(msg)
        return msg
    except Exception as exc:  # noqa: BLE001
        logger.error(f"pg_dump error: {exc}")
        return f"pg_dump error: {exc}"


def restore_postgres_backup(
    backend: DatabaseBackend,
    dump_file: str,
    *,
    drop_first: bool = True,
) -> str:
    """Restore a PostgreSQL backup created with pg_dump (custom format).

    Args:
        backend: A DatabaseBackend configured for PostgreSQL
        dump_file: Path to a pg_dump custom-format .dump file
        drop_first: If True, use pg_restore -c to drop objects before restore

    Returns:
        str: "ok" on success or an error message on failure.
    """
    if backend.backend_type != BackendType.POSTGRESQL:
        msg = "restore_postgres_backup requires a PostgreSQL backend"
        logger.error(msg)
        return msg

    pg_restore = shutil.which("pg_restore")
    if not pg_restore:
        msg = "pg_restore not found on PATH"
        logger.error(msg)
        return msg

    if not os.path.exists(dump_file):
        msg = f"dump not found: {dump_file}"
        logger.error(msg)
        return msg

    config = getattr(backend, "config", None)
    if not config:
        msg = "PostgreSQL backend missing configuration; cannot perform restore"
        logger.error(msg)
        return msg

    host = config.pg_host or "localhost"
    port = str(config.pg_port or 5432)
    dbname = config.pg_database or "tldw"
    user = config.pg_user or "postgres"
    password = config.pg_password or None

    cmd = [
        pg_restore,
        "-h", host,
        "-p", port,
        "-U", user,
        "-d", dbname,
        "-1",              # single transaction
    ]
    if drop_first:
        cmd.append("-c")    # clean (drop) database objects before recreating
    cmd.append(dump_file)

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = str(password)

    try:
        logger.info(f"Running pg_restore on {dump_file} into database '{dbname}'")
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            logger.error(f"pg_restore failed ({proc.returncode}): {proc.stderr.strip()}")
            return f"pg_restore failed: {proc.stderr.strip()}"
        logger.info("PostgreSQL restore completed successfully")
        return "ok"
    except FileNotFoundError:
        msg = "pg_restore executable not found; ensure PostgreSQL client tools are installed"
        logger.error(msg)
        return msg
    except Exception as exc:  # noqa: BLE001
        logger.error(f"pg_restore error: {exc}")
        return f"pg_restore error: {exc}"
