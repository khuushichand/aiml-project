# message_utils.py
# Description: Shared helpers for chat message handling.

from __future__ import annotations

from typing import Optional


def should_persist_message_role(role: Optional[str]) -> bool:
    """Return True when a message role is present and should be persisted."""
    if role is None:
        return False
    if isinstance(role, str):
        return bool(role.strip())
    return True
