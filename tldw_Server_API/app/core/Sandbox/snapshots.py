from __future__ import annotations

import contextlib
import os
import shutil
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

_SNAPSHOTS_NONCRITICAL_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    ConnectionError,
    EOFError,
    FileNotFoundError,
    ImportError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    UnicodeDecodeError,
    ValueError,
    shutil.Error,
    tarfile.TarError,
)


class SnapshotManager:
    """Manages session snapshots for checkpoint/restore workflows.

    Provides the ability to create snapshots of session workspaces,
    restore from snapshots, and clone sessions with their current state.
    """

    def __init__(self, storage_path: str | None = None) -> None:
        """Initialize the snapshot manager.

        Args:
            storage_path: Base path for storing snapshots. Defaults to
                         SANDBOX_SNAPSHOT_PATH env var or /tmp/sandbox_snapshots.
        """
        if storage_path:
            self.storage_path = storage_path
        else:
            self.storage_path = os.getenv(
                "SANDBOX_SNAPSHOT_PATH",
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "tmp_dir", "sandbox_snapshots")
            )
        # Ensure storage directory exists
        try:
            os.makedirs(self.storage_path, exist_ok=True)
        except _SNAPSHOTS_NONCRITICAL_EXCEPTIONS as e:
            logger.warning(f"Failed to create snapshot storage path: {e}")

    def _snapshot_dir(self, session_id: str) -> Path:
        """Get the directory for a session's snapshots."""
        return Path(self.storage_path) / session_id

    def _snapshot_path(self, session_id: str, snapshot_id: str) -> Path:
        """Get the full path for a specific snapshot archive."""
        return self._snapshot_dir(session_id) / f"{snapshot_id}.tar.gz"

    def _metadata_path(self, session_id: str, snapshot_id: str) -> Path:
        """Get the path for a snapshot's metadata file."""
        return self._snapshot_dir(session_id) / f"{snapshot_id}.meta.json"

    def create_snapshot(self, session_id: str, workspace_path: str) -> dict:
        """Create a snapshot of the session workspace.

        Creates a compressed tarball of the workspace directory and stores
        metadata about the snapshot.

        Args:
            session_id: The session ID to associate the snapshot with.
            workspace_path: The path to the workspace directory to snapshot.

        Returns:
            A dictionary containing snapshot_id, created_at, and size_bytes.

        Raises:
            ValueError: If the workspace path doesn't exist or isn't a directory.
            IOError: If there's an error creating the snapshot archive.
        """
        if not workspace_path or not os.path.isdir(workspace_path):
            raise ValueError(f"Invalid workspace path: {workspace_path}")

        snapshot_id = f"snap-{uuid.uuid4().hex[:12]}"
        snapshot_dir = self._snapshot_dir(session_id)
        snapshot_path = self._snapshot_path(session_id, snapshot_id)
        metadata_path = self._metadata_path(session_id, snapshot_id)

        try:
            snapshot_dir.mkdir(parents=True, exist_ok=True)
        except _SNAPSHOTS_NONCRITICAL_EXCEPTIONS as e:
            raise OSError(f"Failed to create snapshot directory: {e}")

        # Create the tarball
        try:
            with tarfile.open(snapshot_path, "w:gz") as tar:
                # Add workspace contents with relative paths
                for item in os.listdir(workspace_path):
                    item_path = os.path.join(workspace_path, item)
                    tar.add(item_path, arcname=item)
        except _SNAPSHOTS_NONCRITICAL_EXCEPTIONS as e:
            # Clean up on failure
            with contextlib.suppress(_SNAPSHOTS_NONCRITICAL_EXCEPTIONS):
                snapshot_path.unlink(missing_ok=True)
            raise OSError(f"Failed to create snapshot archive: {e}")

        # Get snapshot size
        try:
            size_bytes = snapshot_path.stat().st_size
        except _SNAPSHOTS_NONCRITICAL_EXCEPTIONS:
            size_bytes = 0

        # Create metadata
        created_at = datetime.now(timezone.utc).isoformat()
        metadata = {
            "snapshot_id": snapshot_id,
            "session_id": session_id,
            "created_at": created_at,
            "size_bytes": size_bytes,
            "workspace_path": workspace_path,
        }

        # Store metadata
        try:
            import json
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)
        except _SNAPSHOTS_NONCRITICAL_EXCEPTIONS as e:
            logger.warning(f"Failed to write snapshot metadata: {e}")

        return {
            "snapshot_id": snapshot_id,
            "created_at": created_at,
            "size_bytes": size_bytes,
        }

    def restore_snapshot(
        self, session_id: str, snapshot_id: str, workspace_path: str
    ) -> bool:
        """Restore session workspace from a snapshot.

        Clears the current workspace and extracts the snapshot archive.

        Args:
            session_id: The session ID owning the snapshot.
            snapshot_id: The snapshot ID to restore.
            workspace_path: The path to restore the workspace to.

        Returns:
            True if restoration was successful.

        Raises:
            ValueError: If the snapshot or workspace path is invalid.
            IOError: If there's an error extracting the snapshot.
        """
        snapshot_path = self._snapshot_path(session_id, snapshot_id)

        if not snapshot_path.exists():
            raise ValueError(f"Snapshot not found: {snapshot_id}")

        if not workspace_path:
            raise ValueError("Invalid workspace path")

        # Clear current workspace (but keep the directory)
        try:
            if os.path.isdir(workspace_path):
                for item in os.listdir(workspace_path):
                    item_path = os.path.join(workspace_path, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                    else:
                        with contextlib.suppress(_SNAPSHOTS_NONCRITICAL_EXCEPTIONS):
                            os.remove(item_path)
            else:
                os.makedirs(workspace_path, exist_ok=True)
        except _SNAPSHOTS_NONCRITICAL_EXCEPTIONS as e:
            raise OSError(f"Failed to clear workspace: {e}")

        # Extract snapshot
        try:
            with tarfile.open(snapshot_path, "r:gz") as tar:
                # Security: prevent path traversal
                def safe_extract(tar, path):
                    for member in tar.getmembers():
                        member_path = os.path.join(path, member.name)
                        abs_path = os.path.abspath(member_path)
                        if not abs_path.startswith(os.path.abspath(path) + os.sep) and abs_path != os.path.abspath(path):
                            raise ValueError(f"Path traversal detected: {member.name}")
                    tar.extractall(path)

                safe_extract(tar, workspace_path)
        except ValueError:
            raise
        except _SNAPSHOTS_NONCRITICAL_EXCEPTIONS as e:
            raise OSError(f"Failed to extract snapshot: {e}")

        return True

    def clone_session(
        self,
        source_session_id: str,
        source_workspace: str,
        new_session_id: str,
        new_workspace: str,
    ) -> bool:
        """Clone a session by copying its workspace.

        Creates a copy of the source workspace in the new location.

        Args:
            source_session_id: The source session ID (for logging/tracking).
            source_workspace: The path to the source workspace.
            new_session_id: The new session ID (for logging/tracking).
            new_workspace: The path for the new workspace.

        Returns:
            True if cloning was successful.

        Raises:
            ValueError: If paths are invalid.
            IOError: If there's an error copying the workspace.
        """
        if not source_workspace or not os.path.isdir(source_workspace):
            raise ValueError(f"Invalid source workspace: {source_workspace}")

        if not new_workspace:
            raise ValueError("Invalid new workspace path")

        try:
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(new_workspace), exist_ok=True)

            # Copy the workspace
            if os.path.exists(new_workspace):
                shutil.rmtree(new_workspace, ignore_errors=True)

            shutil.copytree(source_workspace, new_workspace, dirs_exist_ok=True)
        except _SNAPSHOTS_NONCRITICAL_EXCEPTIONS as e:
            raise OSError(f"Failed to clone workspace: {e}")

        logger.info(f"Cloned session {source_session_id} to {new_session_id}")
        return True

    def list_snapshots(self, session_id: str) -> list[dict]:
        """List all snapshots for a session.

        Args:
            session_id: The session ID to list snapshots for.

        Returns:
            A list of snapshot metadata dictionaries, sorted by created_at (newest first).
        """
        snapshot_dir = self._snapshot_dir(session_id)

        if not snapshot_dir.exists():
            return []

        snapshots: list[dict] = []
        import json

        for meta_file in snapshot_dir.glob("*.meta.json"):
            try:
                with open(meta_file) as f:
                    metadata = json.load(f)
                    # Verify the actual archive exists
                    snapshot_id = metadata.get("snapshot_id")
                    if snapshot_id:
                        archive_path = self._snapshot_path(session_id, snapshot_id)
                        if archive_path.exists():
                            # Update size in case it changed
                            with contextlib.suppress(_SNAPSHOTS_NONCRITICAL_EXCEPTIONS):
                                metadata["size_bytes"] = archive_path.stat().st_size
                            snapshots.append(metadata)
            except _SNAPSHOTS_NONCRITICAL_EXCEPTIONS as e:
                logger.debug(f"Failed to read snapshot metadata {meta_file}: {e}")

        # Sort by created_at, newest first
        snapshots.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return snapshots

    def delete_snapshot(self, session_id: str, snapshot_id: str) -> bool:
        """Delete a specific snapshot.

        Args:
            session_id: The session ID owning the snapshot.
            snapshot_id: The snapshot ID to delete.

        Returns:
            True if deletion was successful or snapshot didn't exist.
        """
        snapshot_path = self._snapshot_path(session_id, snapshot_id)
        metadata_path = self._metadata_path(session_id, snapshot_id)

        deleted = False

        try:
            if snapshot_path.exists():
                snapshot_path.unlink()
                deleted = True
        except _SNAPSHOTS_NONCRITICAL_EXCEPTIONS as e:
            logger.warning(f"Failed to delete snapshot archive {snapshot_id}: {e}")

        try:
            if metadata_path.exists():
                metadata_path.unlink()
                deleted = True
        except _SNAPSHOTS_NONCRITICAL_EXCEPTIONS as e:
            logger.warning(f"Failed to delete snapshot metadata {snapshot_id}: {e}")

        # Clean up empty session snapshot directory
        try:
            snapshot_dir = self._snapshot_dir(session_id)
            if snapshot_dir.exists() and not any(snapshot_dir.iterdir()):
                snapshot_dir.rmdir()
        except _SNAPSHOTS_NONCRITICAL_EXCEPTIONS:
            pass

        return deleted

    def cleanup_session_snapshots(self, session_id: str) -> int:
        """Delete all snapshots for a session.

        Args:
            session_id: The session ID to clean up.

        Returns:
            The number of snapshots deleted.
        """
        snapshot_dir = self._snapshot_dir(session_id)

        if not snapshot_dir.exists():
            return 0

        count = 0
        try:
            # Count archives before deletion
            count = len(list(snapshot_dir.glob("*.tar.gz")))
            # Remove the entire directory
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        except _SNAPSHOTS_NONCRITICAL_EXCEPTIONS as e:
            logger.warning(f"Failed to cleanup session snapshots: {e}")

        return count

    def get_snapshot_info(self, session_id: str, snapshot_id: str) -> dict | None:
        """Get information about a specific snapshot.

        Args:
            session_id: The session ID owning the snapshot.
            snapshot_id: The snapshot ID to get info for.

        Returns:
            Snapshot metadata dictionary or None if not found.
        """
        metadata_path = self._metadata_path(session_id, snapshot_id)
        snapshot_path = self._snapshot_path(session_id, snapshot_id)

        if not metadata_path.exists() or not snapshot_path.exists():
            return None

        try:
            import json
            with open(metadata_path) as f:
                metadata = json.load(f)
                # Update size
                with contextlib.suppress(_SNAPSHOTS_NONCRITICAL_EXCEPTIONS):
                    metadata["size_bytes"] = snapshot_path.stat().st_size
                return metadata
        except _SNAPSHOTS_NONCRITICAL_EXCEPTIONS as e:
            logger.debug(f"Failed to read snapshot metadata: {e}")
            return None

    def get_total_size(self, session_id: str) -> int:
        """Get the total size of all snapshots for a session.

        Args:
            session_id: The session ID to calculate size for.

        Returns:
            Total size in bytes.
        """
        snapshot_dir = self._snapshot_dir(session_id)

        if not snapshot_dir.exists():
            return 0

        total = 0
        for archive in snapshot_dir.glob("*.tar.gz"):
            with contextlib.suppress(_SNAPSHOTS_NONCRITICAL_EXCEPTIONS):
                total += archive.stat().st_size

        return total

    def enforce_quota(
        self, session_id: str, max_snapshots: int = 10, max_size_mb: int = 256
    ) -> list[str]:
        """Enforce snapshot quotas by deleting old snapshots.

        Deletes oldest snapshots to enforce count and size limits.

        Args:
            session_id: The session ID to enforce quotas for.
            max_snapshots: Maximum number of snapshots to keep.
            max_size_mb: Maximum total size in MB.

        Returns:
            List of deleted snapshot IDs.
        """
        snapshots = self.list_snapshots(session_id)
        deleted: list[str] = []
        max_size_bytes = max_size_mb * 1024 * 1024

        # Delete by count (keep newest)
        while len(snapshots) > max_snapshots:
            oldest = snapshots.pop()  # List is sorted newest first
            snap_id = oldest.get("snapshot_id")
            if snap_id and self.delete_snapshot(session_id, snap_id):
                deleted.append(snap_id)

        # Delete by size (remove oldest until under limit)
        total_size = sum(s.get("size_bytes", 0) for s in snapshots)
        while total_size > max_size_bytes and snapshots:
            oldest = snapshots.pop()
            snap_id = oldest.get("snapshot_id")
            snap_size = oldest.get("size_bytes", 0)
            if snap_id and self.delete_snapshot(session_id, snap_id):
                deleted.append(snap_id)
                total_size -= snap_size

        return deleted
