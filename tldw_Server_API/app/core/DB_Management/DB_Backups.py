# Backup_Manager.py
#
# Imports:
import os
import shutil
import sqlite3
from datetime import datetime
from typing import Dict, Optional

from loguru import logger

# Local Imports:
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Utils.Utils import get_project_relative_path
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
    backup_base_dir = get_project_relative_path('tldw_DB_Backups')
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
