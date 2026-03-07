"""Budget enforcement helpers for deep research sessions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchLimits:
    max_searches: int
    max_fetched_docs: int
    max_runtime_seconds: int


@dataclass(frozen=True)
class ResearchLimitError:
    code: str
    limit_key: str
    limit_value: int
    current_value: int


_LIMIT_FIELD_MAP = {
    "searches": "max_searches",
    "fetched_docs": "max_fetched_docs",
    "runtime_seconds": "max_runtime_seconds",
}


def ensure_limit_available(
    limits: ResearchLimits,
    usage: dict[str, int],
    key: str,
) -> ResearchLimitError | None:
    """Return a structured error when the requested budget is exhausted."""
    field_name = _LIMIT_FIELD_MAP.get(key)
    if field_name is None:
        raise KeyError(key)

    limit_value = int(getattr(limits, field_name))
    current_value = int(usage.get(key, 0))
    if current_value >= limit_value:
        return ResearchLimitError(
            code="research_limit_exceeded",
            limit_key=key,
            limit_value=limit_value,
            current_value=current_value,
        )
    return None
