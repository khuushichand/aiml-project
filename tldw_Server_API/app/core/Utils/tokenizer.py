"""
Simple token counting utilities with configurable strategies.

Strategies:
- whitespace: count whitespace-delimited tokens
- char_approx: approximate by character length (≈4 chars per token)

Configuration via settings (dict-like):
  TOKEN_ESTIMATOR_MODE: "whitespace" | "char_approx"
  TOKEN_CHAR_APPROX_DIVISOR: int (default 4)
"""

from math import ceil
from typing import Optional

try:
    # settings is dict-like per project patterns
    from tldw_Server_API.app.core.config import settings  # type: ignore
except Exception:
    settings = {}


def count_tokens(text: Optional[str], strategy: Optional[str] = None) -> int:
    """
    Count tokens using the configured strategy.

    Args:
        text: input text (None treated as empty)
        strategy: override strategy ("whitespace" | "char_approx")

    Returns:
        Estimated token count as int
    """
    if not text:
        return 0

    chosen = (strategy or settings.get("TOKEN_ESTIMATOR_MODE") or "whitespace").lower()

    if chosen == "char_approx":
        divisor = settings.get("TOKEN_CHAR_APPROX_DIVISOR", 4)
        try:
            div = int(divisor) if int(divisor) > 0 else 4
        except Exception:
            div = 4
        return int(ceil(len(text) / div))

    # default: whitespace
    return len(text.split())
