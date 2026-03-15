# distributed_lock.py
# Description: Distributed lock module for cross-process migration coordination.
#
# Provides:
#   - FileLock: cross-process file-based lock using fcntl
#   - RedisLock: Redis-based distributed lock using SET NX EX
#   - acquire_migration_lock(): context manager factory that picks the best backend
#
from __future__ import annotations

import fcntl
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional

from loguru import logger

try:  # pragma: no cover - import guard
    import redis as _redis_mod  # type: ignore
except ImportError:  # pragma: no cover
    _redis_mod = None  # type: ignore[assignment]


class LockAcquisitionError(RuntimeError):
    """Raised when a distributed lock cannot be acquired within the timeout."""


class FileLock:
    """Cross-process file-based lock using ``fcntl.flock``.

    Parameters:
        path: Path to the lock file.
        timeout: Maximum seconds to wait for lock acquisition.
        stale_timeout: Seconds after which a lock file is considered stale
            (the owning PID is dead or the file is too old).
    """

    def __init__(
        self,
        path: str | Path,
        timeout: float = 60,
        stale_timeout: float = 300,
    ) -> None:
        self.path = Path(path)
        self.timeout = timeout
        self.stale_timeout = stale_timeout
        self._fd: Optional[int] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def acquire(self) -> bool:
        """Try to acquire the lock, retrying until *timeout* expires.

        Returns ``True`` on success, ``False`` if the timeout is reached.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        attempt = 0

        while True:
            attempt += 1
            try:
                fd = os.open(
                    str(self.path),
                    os.O_CREAT | os.O_RDWR,
                    0o644,
                )
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Write our PID so stale detection works from other processes.
                os.ftruncate(fd, 0)
                os.lseek(fd, 0, os.SEEK_SET)
                os.write(fd, f"{os.getpid()}\n".encode())
                os.fsync(fd)
                self._fd = fd
                logger.debug("FileLock acquired: {}", self.path)
                return True
            except OSError:
                # Could not lock — close fd and retry.
                try:
                    os.close(fd)  # type: ignore[possibly-undefined]
                except OSError:
                    pass

                # Try to break stale locks on first failure.
                if attempt == 1:
                    self._break_stale_lock()

                if time.monotonic() >= deadline:
                    return False

                time.sleep(min(0.1, max(0, deadline - time.monotonic())))

    def release(self) -> None:
        """Release the lock and remove the lock file."""
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        # Best-effort removal of the lock file.
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Stale lock detection
    # ------------------------------------------------------------------

    def _break_stale_lock(self) -> None:
        """Remove the lock file if the owning PID is dead or the file is older
        than *stale_timeout* seconds."""
        try:
            if not self.path.exists():
                return

            # Check file age.
            try:
                mtime = self.path.stat().st_mtime
                if (time.time() - mtime) > self.stale_timeout:
                    logger.warning(
                        "Breaking stale lock (age exceeded): {}", self.path
                    )
                    self.path.unlink(missing_ok=True)
                    return
            except OSError:
                return

            # Check if the PID is still alive.
            try:
                content = self.path.read_text().strip()
                pid = int(content)
            except (OSError, ValueError):
                return

            try:
                os.kill(pid, 0)  # Signal 0 — just check existence.
            except ProcessLookupError:
                logger.warning(
                    "Breaking stale lock (PID {} dead): {}", pid, self.path
                )
                self.path.unlink(missing_ok=True)
            except PermissionError:
                # Process exists but we can't signal it — lock is NOT stale.
                pass
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "FileLock":
        if not self.acquire():
            raise LockAcquisitionError(
                f"Failed to acquire file lock {self.path} "
                f"within {self.timeout}s"
            )
        return self

    def __exit__(self, *exc: Any) -> None:
        self.release()


class RedisLock:
    """Redis-based distributed lock using ``SET key NX EX``.

    Uses a unique token per instance and a Lua script for safe release
    (only deletes the key if our token still owns it).

    Parameters:
        redis_client: A synchronous ``redis.Redis``-compatible client.
        key: Redis key to use for the lock.
        timeout: Maximum seconds to wait for lock acquisition.
        ttl: Seconds until the key auto-expires (prevents deadlock on crash).
    """

    _RELEASE_LUA = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    def __init__(
        self,
        redis_client: Any,
        key: str = "tldw:migration:lock",
        timeout: float = 60,
        ttl: int = 300,
    ) -> None:
        self._client = redis_client
        self.key = key
        self.timeout = timeout
        self.ttl = ttl
        self._token: str = uuid.uuid4().hex

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def acquire(self) -> bool:
        """Try ``SET key NX EX`` in a retry loop until *timeout*."""
        deadline = time.monotonic() + self.timeout

        while True:
            result = self._client.set(
                self.key,
                self._token,
                ex=self.ttl,
                nx=True,
            )
            if result:
                logger.debug("RedisLock acquired: {}", self.key)
                return True

            if time.monotonic() >= deadline:
                return False

            time.sleep(min(0.1, max(0, deadline - time.monotonic())))

    def release(self) -> None:
        """Atomically release the lock only if our token still owns it."""
        try:
            self._client.eval(
                self._RELEASE_LUA,
                1,
                self.key,
                self._token,
            )
        except Exception as exc:
            logger.debug("RedisLock release failed (non-critical): {}", exc)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "RedisLock":
        if not self.acquire():
            raise LockAcquisitionError(
                f"Failed to acquire Redis lock '{self.key}' "
                f"within {self.timeout}s"
            )
        return self

    def __exit__(self, *exc: Any) -> None:
        self.release()


# ----------------------------------------------------------------------
# Factory
# ----------------------------------------------------------------------

@contextmanager
def acquire_migration_lock(
    *,
    lock_dir: Optional[str | Path] = None,
    lock_name: str = "db_migration",
    redis_url: Optional[str] = None,
    timeout: float = 60,
) -> Generator[FileLock | RedisLock, None, None]:
    """Context manager that picks the best lock backend.

    If *redis_url* is provided **and** the server is reachable, a
    :class:`RedisLock` is used.  Otherwise falls back to :class:`FileLock`.

    Parameters:
        lock_dir: Directory for file-based locks.  Defaults to ``~/.tldw/locks/``.
        lock_name: Base name for the lock (file or Redis key).
        redis_url: Optional Redis connection URL.
        timeout: Maximum seconds to wait for the lock.
    """
    # Try Redis first.
    if redis_url and _redis_mod is not None:
        try:
            client = _redis_mod.from_url(redis_url, decode_responses=True)
            client.ping()
            key = f"tldw:{lock_name}:lock"
            lock = RedisLock(client, key=key, timeout=timeout)
            with lock:
                yield lock
            return
        except Exception as exc:
            logger.debug(
                "Redis unavailable for migration lock ({}); falling back to file lock",
                exc,
            )

    # Fall back to FileLock.
    if lock_dir is None:
        lock_dir = Path.home() / ".tldw" / "locks"
    lock_path = Path(lock_dir) / f"{lock_name}.lock"
    lock = FileLock(lock_path, timeout=timeout)
    with lock:
        yield lock


__all__ = [
    "LockAcquisitionError",
    "FileLock",
    "RedisLock",
    "acquire_migration_lock",
]
