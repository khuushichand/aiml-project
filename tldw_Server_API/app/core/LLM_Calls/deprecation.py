from __future__ import annotations

from loguru import logger

_WARNED: set[str] = set()


def log_legacy_once(key: str, message: str) -> None:
    if key in _WARNED:
        return
    _WARNED.add(key)
    logger.warning(message)
