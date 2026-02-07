# Storage Module
# Provides abstracted file storage backends for media files
#
# This module supports storing original uploaded files (PDFs, etc.) with
# a pluggable backend architecture for future S3/object storage support.

from tldw_Server_API.app.core.Storage.filesystem_storage import FileSystemStorage
from tldw_Server_API.app.core.Storage.storage_interface import StorageBackend

__all__ = ["StorageBackend", "FileSystemStorage", "get_storage_backend"]


_storage_backend_instance: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    """
    Get the configured storage backend instance.

    Returns a singleton instance of the configured storage backend.
    Currently defaults to FileSystemStorage.
    """
    global _storage_backend_instance

    if _storage_backend_instance is None:
        from pathlib import Path

        from tldw_Server_API.app.core.config import settings

        # Get storage configuration
        storage_type = getattr(settings, 'storage_backend', 'filesystem')

        if storage_type == 'filesystem':
            # Default base path for file storage
            base_path = getattr(
                settings,
                'file_storage_path',
                Path(__file__).parent.parent.parent.parent.parent / "Databases" / "user_files"
            )
            if isinstance(base_path, str):
                base_path = Path(base_path)

            _storage_backend_instance = FileSystemStorage(base_path=base_path)
        else:
            # Future: Add S3 or other backends here
            raise ValueError(f"Unknown storage backend: {storage_type}")

    return _storage_backend_instance


def reset_storage_backend() -> None:
    """Reset the storage backend instance (useful for testing)."""
    global _storage_backend_instance
    _storage_backend_instance = None
