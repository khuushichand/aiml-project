from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import IO, AsyncIterator, Optional

from aiofiles import threadpool as aiofiles_threadpool

from loguru import logger


def resolve_safe_local_path(path: Path, base_dir: Path) -> Optional[Path]:
    """
    Resolve ``path`` relative to ``base_dir`` and validate containment.

    Returns the resolved safe path when valid; otherwise returns None.
    """
    try:
        base_resolved = Path(base_dir).resolve(strict=False)
        path_obj = Path(path)
        path_resolved = (
            path_obj.resolve(strict=False)
            if path_obj.is_absolute()
            else base_resolved.joinpath(path_obj).resolve(strict=False)
        )
        try:
            common_path = os.path.commonpath([str(base_resolved), str(path_resolved)])
        except ValueError:
            logger.warning(
                "Rejected path on different drive for local media source: %s",
                path,
            )
            return None
        if common_path == str(base_resolved):
            return path_resolved
        logger.warning(
            "Rejected path outside of base directory for local media source: %s (base: %s)",
            path_resolved,
            base_resolved,
        )
        return None
    except Exception as exc:
        logger.warning("Error while validating local media path %s: %s", path, exc)
        return None


def is_safe_local_path(path: Path, base_dir: Path) -> bool:
    """
    Validate that ``path`` is a local file path contained within ``base_dir``.

    This helps prevent directory traversal or absolute-path access outside the
    expected base directory when dealing with user-influenced inputs.
    """
    return resolve_safe_local_path(path, base_dir) is not None


def _flags_from_mode(mode: str) -> int:
    if "x" in mode and "+" in mode:
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    elif "x" in mode:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    elif "w" in mode and "+" in mode:
        flags = os.O_RDWR | os.O_CREAT | os.O_TRUNC
    elif "w" in mode:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    elif "a" in mode and "+" in mode:
        flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
    elif "a" in mode:
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    elif "r" in mode and "+" in mode:
        flags = os.O_RDWR
    elif "r" in mode:
        flags = os.O_RDONLY
    else:
        raise ValueError(f"Unsupported file mode: {mode}")

    cloexec = getattr(os, "O_CLOEXEC", 0)
    return flags | cloexec


def _open_safe_posix(
    relative_path: Path,
    base_dir: Path,
    mode: str,
) -> Optional[IO]:
    if not relative_path.parts:
        logger.warning("Rejected empty relative path under base directory: %s", base_dir)
        return None

    nofollow = getattr(os, "O_NOFOLLOW", 0)
    o_directory = getattr(os, "O_DIRECTORY", 0)
    cloexec = getattr(os, "O_CLOEXEC", 0)
    dir_flags = os.O_RDONLY | o_directory | cloexec
    dir_flags_no_follow = dir_flags | nofollow
    current_fd = None
    try:
        current_fd = os.open(base_dir, dir_flags)
        for part in relative_path.parts[:-1]:
            next_fd = os.open(part, dir_flags_no_follow, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        file_flags = _flags_from_mode(mode) | nofollow
        fd = os.open(relative_path.parts[-1], file_flags, dir_fd=current_fd)
        return os.fdopen(fd, mode)
    except Exception as exc:
        logger.warning(
            "Secure open failed for %s under %s: %s",
            relative_path,
            base_dir,
            exc,
        )
        return None
    finally:
        if current_fd is not None:
            try:
                os.close(current_fd)
            except Exception:
                logger.debug("Failed to close directory fd for %s", base_dir)


def _open_safe_windows(
    safe_path: Path,
    base_dir: Path,
    mode: str,
) -> Optional[IO]:
    try:
        handle = open(safe_path, mode)
    except Exception as exc:
        logger.warning("Failed to open %s: %s", safe_path, exc)
        return None

    try:
        base_real = os.path.normcase(os.path.realpath(base_dir))
        handle_real = os.path.normcase(os.path.realpath(handle.name))
        if os.path.commonpath([base_real, handle_real]) != base_real:
            logger.warning(
                "Rejected path outside base directory after open: %s (base: %s)",
                handle_real,
                base_real,
            )
            handle.close()
            return None
    except Exception as exc:
        logger.warning("Failed to validate opened path %s: %s", safe_path, exc)
        try:
            handle.close()
        except Exception:
            logger.debug("Failed to close handle for %s", safe_path)
        return None
    return handle


def open_safe_local_path(
    path: Path,
    base_dir: Path,
    *,
    mode: str = "rb",
) -> Optional[IO]:
    """
    Open a local file under ``base_dir`` with best-effort protections against traversal.

    On POSIX platforms, this walks the path using ``dir_fd`` and ``O_NOFOLLOW`` to
    reject symlinks. On Windows, it performs a pre-check and a post-open realpath
    validation as a safer fallback, but reparse points can still be swapped after
    opening; treat this as best-effort and keep an explicit allowlist base directory.
    """
    base_resolved = Path(base_dir).resolve(strict=False)
    safe_path = resolve_safe_local_path(path, base_resolved)
    if safe_path is None:
        return None
    try:
        relative_path = safe_path.relative_to(base_resolved)
    except ValueError:
        logger.warning(
            "Rejected path outside of base directory for secure open: %s (base: %s)",
            safe_path,
            base_resolved,
        )
        return None

    if os.name == "nt":
        return _open_safe_windows(safe_path, base_resolved, mode)

    return _open_safe_posix(relative_path, base_resolved, mode)


@asynccontextmanager
async def open_safe_local_path_async(
    path: Path,
    base_dir: Path,
    *,
    mode: str = "rb",
) -> AsyncIterator[Optional[IO]]:
    """
    Async wrapper around ``open_safe_local_path`` that returns an aiofiles handle.

    When the path is rejected, yields None.
    """
    handle = open_safe_local_path(path, base_dir, mode=mode)
    if handle is None:
        yield None
        return
    wrapped = aiofiles_threadpool.wrap(handle)
    try:
        yield wrapped
    finally:
        try:
            await wrapped.close()
        except Exception:
            logger.debug("Failed to close async handle for %s", path)
