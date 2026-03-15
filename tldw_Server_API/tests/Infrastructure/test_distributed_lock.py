# test_distributed_lock.py
"""Tests for the distributed lock module."""

import os
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tldw_Server_API.app.core.Infrastructure.distributed_lock import (
    FileLock,
    LockAcquisitionError,
    RedisLock,
    acquire_migration_lock,
)


# ======================================================================
# FileLock tests
# ======================================================================


class TestFileLockAcquireRelease:
    """Basic acquire / release behaviour."""

    def test_acquire_and_release(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path, timeout=5)

        assert lock.acquire() is True
        assert lock_path.exists()
        # Lock file should contain our PID.
        content = lock_path.read_text().strip()
        assert content == str(os.getpid())

        lock.release()
        # Lock file removed after release.
        assert not lock_path.exists()

    def test_acquire_creates_parent_dirs(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "sub" / "dir" / "test.lock"
        lock = FileLock(lock_path, timeout=2)
        assert lock.acquire() is True
        lock.release()

    def test_release_idempotent(self, tmp_path: Path) -> None:
        lock = FileLock(tmp_path / "test.lock", timeout=2)
        lock.acquire()
        lock.release()
        lock.release()  # Should not raise.


class TestFileLockContextManager:
    """Context manager protocol."""

    def test_context_manager_acquires_and_releases(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "ctx.lock"
        with FileLock(lock_path, timeout=5) as lock:
            assert lock_path.exists()
            assert isinstance(lock, FileLock)
        assert not lock_path.exists()

    def test_context_manager_raises_on_timeout(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "timeout.lock"

        # Hold the lock from the main thread via a raw fd.
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

        try:
            with pytest.raises(LockAcquisitionError):
                # Very short timeout so the test is fast.
                with FileLock(lock_path, timeout=0.3, stale_timeout=9999):
                    pass  # Should never reach here.
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


class TestFileLockConcurrency:
    """Second lock holder should be blocked."""

    def test_second_lock_times_out(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "concurrent.lock"
        lock1 = FileLock(lock_path, timeout=5)
        assert lock1.acquire() is True

        # A second lock with a short timeout should fail.
        lock2 = FileLock(lock_path, timeout=0.3, stale_timeout=9999)
        assert lock2.acquire() is False

        lock1.release()

        # Now lock2 should succeed.
        assert lock2.acquire() is True
        lock2.release()


class TestFileLockStaleLock:
    """Stale lock detection based on dead PID."""

    def test_breaks_stale_lock_dead_pid(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "stale.lock"
        # Write a PID that almost certainly doesn't exist.
        lock_path.write_text("999999999\n")

        lock = FileLock(lock_path, timeout=2, stale_timeout=9999)
        assert lock.acquire() is True
        lock.release()

    def test_breaks_stale_lock_old_file(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "old.lock"
        lock_path.write_text(f"{os.getpid()}\n")
        # Set mtime far in the past.
        old_time = time.time() - 1000
        os.utime(str(lock_path), (old_time, old_time))

        lock = FileLock(lock_path, timeout=2, stale_timeout=60)
        assert lock.acquire() is True
        lock.release()


# ======================================================================
# RedisLock tests (mocked)
# ======================================================================


class _MockRedis:
    """Minimal mock that simulates ``SET ... NX EX`` and ``EVAL``."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int = 0, nx: bool = False):
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True

    def eval(self, script: str, num_keys: int, *args):
        key = args[0]
        token = args[1]
        if self._store.get(key) == token:
            del self._store[key]
            return 1
        return 0

    def ping(self):
        return True


class TestRedisLock:
    """RedisLock with a mock Redis client."""

    def test_acquire_and_release(self) -> None:
        client = _MockRedis()
        lock = RedisLock(client, key="test:lock", timeout=5)

        assert lock.acquire() is True
        assert "test:lock" in client._store

        lock.release()
        assert "test:lock" not in client._store

    def test_context_manager(self) -> None:
        client = _MockRedis()
        with RedisLock(client, key="test:ctx", timeout=5) as lock:
            assert "test:ctx" in client._store
        assert "test:ctx" not in client._store

    def test_second_lock_times_out(self) -> None:
        client = _MockRedis()
        lock1 = RedisLock(client, key="test:dup", timeout=5)
        assert lock1.acquire() is True

        lock2 = RedisLock(client, key="test:dup", timeout=0.2)
        assert lock2.acquire() is False

        lock1.release()

    def test_release_wrong_token_noop(self) -> None:
        client = _MockRedis()
        lock = RedisLock(client, key="test:tok", timeout=5)
        lock.acquire()
        # Simulate another owner.
        client._store["test:tok"] = "someone_else"
        lock.release()
        # Key should still be there (not deleted by our lock).
        assert client._store.get("test:tok") == "someone_else"

    def test_context_manager_raises_on_timeout(self) -> None:
        client = _MockRedis()
        # Pre-fill the key so NX always fails.
        client._store["test:fail"] = "other"

        with pytest.raises(LockAcquisitionError):
            with RedisLock(client, key="test:fail", timeout=0.2):
                pass


# ======================================================================
# acquire_migration_lock factory tests
# ======================================================================


class TestAcquireMigrationLock:
    """Factory context manager selects the right backend."""

    def test_returns_file_lock_by_default(self, tmp_path: Path) -> None:
        with acquire_migration_lock(
            lock_dir=str(tmp_path), lock_name="test_migration", timeout=5
        ) as lock:
            assert isinstance(lock, FileLock)

    def test_file_lock_uses_default_dir_when_none(self) -> None:
        with acquire_migration_lock(lock_name="default_dir_test", timeout=5) as lock:
            assert isinstance(lock, FileLock)
            assert ".tldw" in str(lock.path)
        # Clean up.
        try:
            lock.path.unlink(missing_ok=True)
        except OSError:
            pass

    def test_falls_back_to_file_when_redis_unavailable(self, tmp_path: Path) -> None:
        with acquire_migration_lock(
            lock_dir=str(tmp_path),
            lock_name="fallback",
            redis_url="redis://127.0.0.1:1",  # Non-routable port.
            timeout=5,
        ) as lock:
            assert isinstance(lock, FileLock)

    def test_uses_redis_when_available(self, tmp_path: Path) -> None:
        mock_client = _MockRedis()
        mock_from_url = MagicMock(return_value=mock_client)

        with patch(
            "tldw_Server_API.app.core.Infrastructure.distributed_lock._redis_mod"
        ) as mock_redis:
            mock_redis.from_url = mock_from_url

            with acquire_migration_lock(
                lock_dir=str(tmp_path),
                lock_name="redis_test",
                redis_url="redis://localhost:6379",
                timeout=5,
            ) as lock:
                assert isinstance(lock, RedisLock)
