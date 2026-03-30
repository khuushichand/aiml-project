"""
runtime_flags.py

Shared OSS billing runtime flags.
"""
from __future__ import annotations


def is_billing_enabled() -> bool:
    """OSS builds do not expose the commercial payment runtime."""
    return False
