# db_path_utils.py
"""
Centralized database path management utilities.
Ensures consistent database file locations across the application.
"""

import hashlib
import os
import re
from pathlib import Path
from typing import Callable, Dict, Optional, Union
from loguru import logger

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.testing import is_test_mode
from tldw_Server_API.app.core.Utils.Utils import get_project_root
from tldw_Server_API.app.core.exceptions import InvalidStoragePathError, StorageUnavailableError


UserId = Union[int, str]
_SAFE_TEST_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_SAFE_OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _is_test_context() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST")) or is_test_mode()


def _normalize_user_id(user_id: UserId) -> str:
    raw = str(user_id).strip()
    if not raw:
        raise ValueError("user_id must not be empty for filesystem path")
    if raw.isdigit():
        if int(raw) < 1:
            raise ValueError(f"user_id must be a positive integer for filesystem path: {user_id!r}")
        return raw
    if _is_test_context():
        if (
            _SAFE_TEST_USER_ID_RE.fullmatch(raw)
            and raw[0].isalnum()
            and raw[-1].isalnum()
        ):
            return raw
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"u_{digest}"
    raise ValueError(f"Invalid user_id for filesystem path: {user_id!r}")


def normalize_output_storage_filename(
    storage_path: str | Path,
    *,
    allow_absolute: bool,
    reject_relative_with_separators: bool,
    expand_user: bool = False,
    base_resolved: Optional[Path] = None,
    check_relative_containment: bool = False,
    require_parent_base: bool = False,
    log_message: Optional[Callable[[str], None]] = None,
    log_prefix: Optional[str] = None,
) -> str:
    """Normalize and validate an output storage path, returning a safe filename."""
    def _log(message: str) -> None:
        if log_message is None:
            return
        if log_prefix:
            log_message(f"{log_prefix}: {message}")
        else:
            log_message(message)

    def _fail(message: str, exc: Optional[Exception] = None) -> None:
        _log(message)
        if exc is None:
            raise InvalidStoragePathError("invalid_path")
        raise InvalidStoragePathError("invalid_path") from exc

    storage_path_str = str(storage_path)

    if not check_relative_containment and isinstance(storage_path, str):
        if (
            _SAFE_OUTPUT_NAME_RE.match(storage_path)
            and os.sep not in storage_path
            and (os.altsep is None or os.altsep not in storage_path)
        ):
            return storage_path

    candidate = Path(storage_path_str)
    if expand_user:
        candidate = candidate.expanduser()

    if candidate.is_absolute():
        if not allow_absolute:
            _fail(f"absolute paths are not allowed for outputs: {candidate}")
    elif reject_relative_with_separators and (
        os.sep in storage_path_str or (os.altsep and os.altsep in storage_path_str)
    ):
        _fail("nested output paths are not allowed")

    candidate_name = candidate.name
    if not candidate_name:
        _fail(f"empty output path component from {storage_path!r}")
    if os.sep in candidate_name or (os.altsep and os.altsep in candidate_name):
        _fail(f"path separator detected in output filename: {candidate_name!r}")
    if not _SAFE_OUTPUT_NAME_RE.match(candidate_name):
        _fail(f"invalid characters in output filename: {candidate_name!r}")

    if candidate.is_absolute():
        if base_resolved is None:
            _fail("outputs base directory unavailable for absolute path validation")
        try:
            resolved = candidate.resolve(strict=False)
        except Exception as exc:
            _fail(f"invalid output path {storage_path}: {exc}", exc)
        if not resolved.is_relative_to(base_resolved):
            _fail(f"output path outside base dir: {resolved}")
        if require_parent_base and resolved.parent != base_resolved:
            _fail(f"output path outside base dir: {resolved}")
    elif check_relative_containment:
        if base_resolved is None:
            _fail("outputs base directory unavailable for path validation")
        try:
            resolved = (base_resolved / candidate_name).resolve(strict=False)
        except Exception as exc:
            _fail(f"invalid output path {storage_path}: {exc}", exc)
        if not resolved.is_relative_to(base_resolved):
            _fail(f"output path outside base dir: {resolved}")

    return candidate_name



class DatabasePaths:
    """Centralized database path management."""

    # Database file names
    MEDIA_DB_NAME = "Media_DB_v2.db"
    CHACHA_DB_NAME = "ChaChaNotes.db"
    PROMPTS_DB_NAME = "user_prompts_v2.sqlite"
    AUDIT_DB_NAME = "unified_audit.db"
    EVALUATIONS_DB_NAME = "evaluations.db"
    PERSONALIZATION_DB_NAME = "Personalization.db"
    WORKFLOWS_DB_NAME = "workflows.db"
    WORKFLOWS_SCHEDULER_DB_NAME = "workflows_scheduler.db"
    KANBAN_DB_NAME = "Kanban.db"

    # Subdirectories
    PROMPTS_SUBDIR = "prompts_user_dbs"
    AUDIT_SUBDIR = "audit"
    EVALUATIONS_SUBDIR = "evaluations"
    WORKFLOWS_SUBDIR = "workflows"

    @staticmethod
    def get_user_base_directory(user_id: UserId) -> Path:
        """
        Get the base directory for a specific user's databases.

        Args:
            user_id: The user's ID

        Returns:
            Path to the user's database directory
        """
        user_db_base = os.getenv("USER_DB_BASE_DIR") or settings.get("USER_DB_BASE_DIR")
        project_root = Path(get_project_root())
        if not user_db_base:
            # Fallback to default location
            base_path = project_root / "Databases" / "user_databases"
            logger.warning(f"USER_DB_BASE_DIR not configured, using fallback: {base_path}")
        else:
            base_path = Path(user_db_base).expanduser()
            if not base_path.is_absolute():
                base_path = (project_root / base_path).resolve()
            else:
                base_path = base_path.resolve()

        # Normalize and validate user_id to ensure it is safe as a single path segment
        safe_user_id = _normalize_user_id(user_id)

        # Construct and normalize user directory and ensure it stays under base_path
        user_dir = (base_path / safe_user_id).resolve()
        try:
            user_dir.relative_to(base_path)
        except ValueError as exc:
            raise ValueError(f"Computed user directory escapes base path: {user_dir!r}") from exc

        # Ensure directory exists
        try:
            user_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured user directory exists: {user_dir}")
        except OSError as e:
            logger.error(f"Failed to create user directory {user_dir}: {e}")
            raise StorageUnavailableError("Failed to create user directory") from e

        return user_dir

    @staticmethod
    def get_media_db_path(user_id: UserId) -> Path:
        """Get the path to the user's media database."""
        user_dir = DatabasePaths.get_user_base_directory(user_id)
        return user_dir / DatabasePaths.MEDIA_DB_NAME

    @staticmethod
    def get_chacha_db_path(user_id: UserId) -> Path:
        """Get the path to the user's ChaChaNotes database."""
        user_dir = DatabasePaths.get_user_base_directory(user_id)
        return user_dir / DatabasePaths.CHACHA_DB_NAME

    @staticmethod
    def get_prompts_db_path(user_id: UserId) -> Path:
        """Get the path to the user's prompts database."""
        user_dir = DatabasePaths.get_user_base_directory(user_id)
        prompts_dir = user_dir / DatabasePaths.PROMPTS_SUBDIR

        # Ensure prompts subdirectory exists
        try:
            prompts_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create prompts directory {prompts_dir}: {e}")
            raise StorageUnavailableError("Failed to create prompts directory") from e

        return prompts_dir / DatabasePaths.PROMPTS_DB_NAME

    @staticmethod
    def get_audit_db_path(user_id: UserId) -> Path:
        """Get the path to the user's audit database."""
        user_dir = DatabasePaths.get_user_base_directory(user_id)
        audit_dir = user_dir / DatabasePaths.AUDIT_SUBDIR

        # Ensure audit subdirectory exists
        try:
            audit_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create audit directory {audit_dir}: {e}")
            raise StorageUnavailableError("Failed to create audit directory") from e

        return audit_dir / DatabasePaths.AUDIT_DB_NAME

    @staticmethod
    def get_evaluations_db_path(user_id: UserId) -> Path:
        """Get the path to the user's evaluations database."""
        user_dir = DatabasePaths.get_user_base_directory(user_id)
        eval_dir = user_dir / DatabasePaths.EVALUATIONS_SUBDIR

        # Ensure evaluations subdirectory exists
        try:
            eval_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create evaluations directory {eval_dir}: {e}")
            raise StorageUnavailableError("Failed to create evaluations directory") from e

        return eval_dir / DatabasePaths.EVALUATIONS_DB_NAME

    @staticmethod
    def get_personalization_db_path(user_id: UserId) -> Path:
        """Get the path to the user's Personalization database."""
        user_dir = DatabasePaths.get_user_base_directory(user_id)
        # Keep at root of user dir alongside ChaChaNotes for discoverability
        return user_dir / DatabasePaths.PERSONALIZATION_DB_NAME

    @staticmethod
    def get_workflows_db_path(user_id: UserId) -> Path:
        """Get the path to the user's workflows database."""
        user_dir = DatabasePaths.get_user_base_directory(user_id)
        workflows_dir = user_dir / DatabasePaths.WORKFLOWS_SUBDIR
        try:
            workflows_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create workflows directory {workflows_dir}: {e}")
            raise StorageUnavailableError("Failed to create workflows directory") from e
        return workflows_dir / DatabasePaths.WORKFLOWS_DB_NAME

    @staticmethod
    def get_workflows_scheduler_db_path(user_id: UserId) -> Path:
        """Get the path to the user's workflows scheduler database."""
        user_dir = DatabasePaths.get_user_base_directory(user_id)
        workflows_dir = user_dir / DatabasePaths.WORKFLOWS_SUBDIR
        try:
            workflows_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create workflows scheduler directory {workflows_dir}: {e}")
            raise StorageUnavailableError("Failed to create workflows scheduler directory") from e
        return workflows_dir / DatabasePaths.WORKFLOWS_SCHEDULER_DB_NAME

    @staticmethod
    def get_kanban_db_path(user_id: UserId) -> Path:
        """Get the path to the user's Kanban database."""
        user_dir = DatabasePaths.get_user_base_directory(user_id)
        # Keep at root of user dir alongside ChaChaNotes for discoverability
        return user_dir / DatabasePaths.KANBAN_DB_NAME

    @staticmethod
    def get_all_user_db_paths(user_id: UserId) -> Dict[str, Path]:
        """
        Get all database paths for a user.

        Returns:
            Dictionary mapping database types to their paths
        """
        return {
            "media": DatabasePaths.get_media_db_path(user_id),
            "chacha": DatabasePaths.get_chacha_db_path(user_id),
            "prompts": DatabasePaths.get_prompts_db_path(user_id),
            "audit": DatabasePaths.get_audit_db_path(user_id),
            "evaluations": DatabasePaths.get_evaluations_db_path(user_id),
            "personalization": DatabasePaths.get_personalization_db_path(user_id),
            "workflows": DatabasePaths.get_workflows_db_path(user_id),
            "workflows_scheduler": DatabasePaths.get_workflows_scheduler_db_path(user_id),
            "kanban": DatabasePaths.get_kanban_db_path(user_id),
        }

    @staticmethod
    def validate_database_structure(user_id: UserId) -> bool:
        """
        Validate that all required directories exist for a user.

        Args:
            user_id: The user's ID

        Returns:
            True if all directories exist or were created successfully
        """
        try:
            paths = DatabasePaths.get_all_user_db_paths(user_id)
            logger.info(f"Database structure validated for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to validate database structure for user {user_id}: {e}")
            return False

    @staticmethod
    def get_single_user_id() -> int:
        """
        Get the user ID for single-user mode.

        Returns:
            The configured single-user ID (typically 1)
        """
        return int(settings.get("SINGLE_USER_FIXED_ID", "1"))


# Convenience functions for backward compatibility
def get_user_media_db_path(user_id: UserId) -> str:
    """Get the media database path for a user (returns string for compatibility)."""
    return str(DatabasePaths.get_media_db_path(user_id))


def get_user_chacha_db_path(user_id: UserId) -> str:
    """Get the ChaChaNotes database path for a user (returns string for compatibility)."""
    return str(DatabasePaths.get_chacha_db_path(user_id))


def get_user_prompts_db_path(user_id: UserId) -> str:
    """Get the prompts database path for a user (returns string for compatibility)."""
    return str(DatabasePaths.get_prompts_db_path(user_id))


def ensure_user_database_structure(user_id: UserId) -> bool:
    """
    Ensure all database directories exist for a user.

    Args:
        user_id: The user's ID

    Returns:
        True if successful
    """
    return DatabasePaths.validate_database_structure(user_id)
