"""
Stateless payload management service.
Handles large payloads with external storage and compression.
"""

import gzip
import hashlib
import json
import pickle
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from ..base.exceptions import PayloadError
from ..base.queue_backend import QueueBackend
from ..config import SchedulerConfig


class PayloadService:
    """
    Manages task payloads without maintaining state.

    Handles:
    - Large payload external storage
    - Payload compression
    - Payload cleanup
    - Serialization/deserialization
    """

    _PAYLOAD_REF_PATTERN = re.compile(r"^[a-f0-9]{16,64}$")
    _MAX_HEADER_SIZE_BYTES = 64 * 1024

    def __init__(self, backend: QueueBackend, config: SchedulerConfig):
        """
        Initialize payload service.

        Args:
            backend: Queue backend
            config: Scheduler configuration
        """
        self.backend = backend
        self.config = config
        self.storage_path = config.payload_storage_path
        self.allow_legacy_pickle_payloads = bool(
            getattr(config, 'allow_legacy_pickle_payloads', False)
        )

        # Ensure storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def should_externalize(self, payload: Any) -> bool:
        """
        Check if payload should be stored externally.

        Args:
            payload: Payload to check

        Returns:
            True if payload should be externalized
        """
        try:
            data, _ = self._serialize_payload(payload)
            return len(data) > self.config.payload_threshold_bytes
        except PayloadError:
            return False

    async def store_payload(self, task_id: str, payload: Any) -> Optional[str]:
        """
        Store payload externally if needed.

        Args:
            task_id: Task ID
            payload: Payload to store

        Returns:
            Payload reference if externalized, None otherwise
        """
        if not self.should_externalize(payload):
            return None

        try:
            # Serialize payload
            data, format_type = self._serialize_payload(payload)

            # Optionally compress
            compressed = False
            if self.config.payload_compression and len(data) > 1024:
                original_size = len(data)
                data = gzip.compress(data)
                compressed = True
                logger.debug(
                    f"Compressed payload for task {task_id}: "
                    f"{original_size} -> {len(data)} bytes"
                )

            # Generate reference ID
            payload_ref = hashlib.sha256(
                f"{task_id}_{datetime.now(timezone.utc).isoformat()}".encode()
            ).hexdigest()[:16]

            # Store to file
            file_path = self._get_payload_path(payload_ref)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write metadata and data
            metadata = {
                'task_id': task_id,
                'format': format_type,
                'compressed': compressed,
                'size': len(data),
                'created_at': datetime.now(timezone.utc).isoformat()
            }

            with open(file_path, 'wb') as f:
                # Write metadata as JSON header
                header = json.dumps(metadata).encode('utf-8')
                f.write(len(header).to_bytes(4, 'little'))
                f.write(header)
                f.write(data)

            logger.debug(f"Stored external payload {payload_ref} for task {task_id}")
            return payload_ref

        except Exception as e:
            logger.error(f"Failed to store payload for task {task_id}: {e}")
            raise PayloadError(f"Payload storage failed: {e}") from e

    async def load_payload(self, payload_ref: str) -> Any:
        """
        Load externally stored payload.

        Args:
            payload_ref: Payload reference

        Returns:
            Deserialized payload
        """
        file_path = self._get_payload_path(payload_ref)

        if not file_path.exists():
            raise PayloadError(f"Payload {payload_ref} not found")

        try:
            header, data = self._read_payload_file(file_path)

            # Decompress if needed
            if header.get('compressed'):
                data = gzip.decompress(data)

            # Deserialize based on format
            if header['format'] == 'json':
                return json.loads(data.decode('utf-8'))
            elif header['format'] == 'pickle':
                if not self.allow_legacy_pickle_payloads:
                    raise PayloadError(
                        "Legacy pickle payload loading is disabled. "
                        "Set SCHEDULER_ALLOW_LEGACY_PICKLE_PAYLOADS=true "
                        "to enable compatibility mode."
                    )
                return pickle.loads(data)
            else:
                raise PayloadError(f"Unknown payload format: {header['format']}")

        except Exception as e:
            logger.error(f"Failed to load payload {payload_ref}: {e}")
            raise PayloadError(f"Payload load failed: {e}") from e

    async def delete_payload(self, payload_ref: str) -> bool:
        """
        Delete externally stored payload.

        Args:
            payload_ref: Payload reference

        Returns:
            True if deleted
        """
        file_path = self._get_payload_path(payload_ref)

        if file_path.exists():
            try:
                file_path.unlink()
                logger.debug(f"Deleted payload {payload_ref}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete payload {payload_ref}: {e}")

        return False

    async def cleanup_old_payloads(self, retention_days: Optional[int] = None) -> int:
        """
        Clean up old payload files.

        Args:
            retention_days: Days to retain (uses config if not specified)

        Returns:
            Number of files deleted
        """
        if retention_days is None:
            retention_days = self.config.payload_retention_days

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted = 0

        try:
            for file_path in self.storage_path.rglob("*.payload"):
                try:
                    # Read metadata to check age
                    header, _ = self._read_payload_file(file_path)

                    created_at = datetime.fromisoformat(header['created_at'])
                    if created_at < cutoff:
                        file_path.unlink()
                        deleted += 1

                except Exception as e:
                    logger.warning(f"Failed to process payload file {file_path}: {e}")

            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old payload files")

        except Exception as e:
            logger.error(f"Payload cleanup failed: {e}")

        return deleted

    def _get_payload_path(self, payload_ref: str) -> Path:
        """
        Get file path for payload reference.

        Args:
            payload_ref: Payload reference

        Returns:
            Path to payload file
        """
        self._validate_payload_ref(payload_ref)

        # Use first 2 chars for directory sharding
        shard = payload_ref[:2]
        file_path = (self.storage_path / shard / f"{payload_ref}.payload").resolve()
        storage_root = self.storage_path.resolve()

        if storage_root not in file_path.parents:
            raise PayloadError("Invalid payload reference path")

        return file_path

    async def get_stats(self) -> dict[str, Any]:
        """
        Get payload storage statistics.

        Returns:
            Statistics dictionary
        """
        total_files = 0
        total_size = 0

        try:
            for file_path in self.storage_path.rglob("*.payload"):
                total_files += 1
                total_size += file_path.stat().st_size
        except Exception as e:
            logger.error(f"Failed to get payload stats: {e}")

        return {
            'storage_path': str(self.storage_path),
            'total_files': total_files,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'threshold_bytes': self.config.payload_threshold_bytes,
            'compression_enabled': self.config.payload_compression,
            'allow_legacy_pickle_payloads': self.allow_legacy_pickle_payloads,
            'retention_days': self.config.payload_retention_days
        }

    def prepare_payload(self, payload: Any) -> dict[str, Any]:
        """
        Prepare payload for task creation.

        Validates and potentially modifies payload for storage.

        Args:
            payload: Raw payload

        Returns:
            Prepared payload
        """
        if payload is None:
            return {}

        # Ensure payload is JSON serializable.
        try:
            json.dumps(payload)
            return payload
        except (TypeError, ValueError):
            # Try to make it serializable
            if hasattr(payload, '__dict__'):
                candidate = payload.__dict__
                try:
                    json.dumps(candidate)
                    return candidate
                except (TypeError, ValueError):
                    pass

            logger.warning("Payload not JSON serializable, coercing to safe string payload")
            return {'__non_serializable__': str(payload)}

    def _serialize_payload(self, payload: Any) -> tuple[bytes, str]:
        """Serialize payload into bytes and return format marker."""
        try:
            return json.dumps(payload).encode('utf-8'), 'json'
        except (TypeError, ValueError):
            if self.allow_legacy_pickle_payloads:
                logger.warning("Using legacy pickle payload serialization compatibility mode")
                return pickle.dumps(payload), 'pickle'
            raise PayloadError(
                "Payload must be JSON serializable for external storage. "
                "Set SCHEDULER_ALLOW_LEGACY_PICKLE_PAYLOADS=true for legacy compatibility."
            )

    def _validate_payload_ref(self, payload_ref: str) -> None:
        """Validate payload reference format."""
        if not isinstance(payload_ref, str):
            raise PayloadError("Payload reference must be a string")
        if not self._PAYLOAD_REF_PATTERN.fullmatch(payload_ref):
            raise PayloadError("Invalid payload reference format")

    def _read_payload_file(self, file_path: Path) -> tuple[dict[str, Any], bytes]:
        """Read and validate payload file header/data."""
        with open(file_path, 'rb') as f:
            header_size_raw = f.read(4)
            if len(header_size_raw) != 4:
                raise PayloadError("Invalid payload file header")

            header_size = int.from_bytes(header_size_raw, 'little')
            if header_size <= 0 or header_size > self._MAX_HEADER_SIZE_BYTES:
                raise PayloadError(f"Invalid payload header size: {header_size}")

            header_raw = f.read(header_size)
            if len(header_raw) != header_size:
                raise PayloadError("Corrupt payload header")

            header = json.loads(header_raw.decode('utf-8'))
            if not isinstance(header, dict):
                raise PayloadError("Invalid payload metadata")

            data = f.read()

        return header, data
