"""Lightweight audio streaming exceptions.

Keep these in a minimal module so route-layer imports do not need to load the
full streaming backend stack.
"""


class QuotaExceeded(Exception):
    """Raised when an audio streaming quota is exhausted."""

    def __init__(self, quota: str):
        super().__init__(quota)
        self.quota = quota


__all__ = ["QuotaExceeded"]
