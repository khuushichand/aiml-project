from __future__ import annotations

"""
Helpers for cross-category "cost unit" budgeting backed by ResourceDailyLedger.

This module provides:
- compute_cost_units: convert tokens/requests/minutes into a unified integer
  "cost units" value using simple, env-tunable weights.
- record_cost_units_for_entity: persist daily cost-unit usage into the shared
  ResourceDailyLedger for analytics and optional budget enforcement.
- remaining_daily_cost_units: convenience helper to query remaining budget
  for a given entity and daily cap.

The defaults are intentionally conservative and aimed at v1.1 analytics use:
budgets are only enforced by callers that explicitly consult these helpers.
"""

import math
import os
from datetime import datetime, timezone

from loguru import logger

from tldw_Server_API.app.core.DB_Management.Resource_Daily_Ledger import (
    LedgerEntry,
    ResourceDailyLedger,
)


def _env_positive_int(name: str, default: int) -> int:
    """Return a positive integer from env or the provided default."""
    try:
        raw = os.getenv(name)
        if raw is None:
            return int(default)
        value = int(str(raw).strip())
        return value if value > 0 else int(default)
    except Exception:
        return int(default)


def compute_cost_units(
    *,
    tokens: int = 0,
    minutes: float = 0.0,
    requests: int = 0,
) -> int:
    """
    Compute a unified "cost units" value from tokens, minutes, and requests.

    The mapping is controlled by env-based weights:
    - RG_COST_UNITS_TOKENS_PER_UNIT (default: 1000 tokens → 1 unit)
    - RG_COST_UNITS_MINUTES_PER_UNIT (default: 1 minute → 1 unit)
    - RG_COST_UNITS_REQUESTS_PER_UNIT (default: 1 request → 1 unit)

    Each component contributes ceil(consumption / per_unit) units so that any
    non-zero usage is charged at least 1 unit.
    """
    t = max(0, int(tokens))
    r = max(0, int(requests))
    m = max(0.0, float(minutes))

    tokens_per_unit = _env_positive_int("RG_COST_UNITS_TOKENS_PER_UNIT", 1000)
    minutes_per_unit = _env_positive_int("RG_COST_UNITS_MINUTES_PER_UNIT", 1)
    requests_per_unit = _env_positive_int("RG_COST_UNITS_REQUESTS_PER_UNIT", 1)

    units = 0
    if t > 0 and tokens_per_unit > 0:
        units += int(math.ceil(t / float(tokens_per_unit)))
    if m > 0.0 and minutes_per_unit > 0:
        units += int(math.ceil(m / float(minutes_per_unit)))
    if r > 0 and requests_per_unit > 0:
        units += int(math.ceil(r / float(requests_per_unit)))
    return units


async def record_cost_units_for_entity(
    *,
    entity_scope: str,
    entity_value: str,
    tokens: int = 0,
    minutes: float = 0.0,
    requests: int = 0,
    op_id: str | None = None,
    occurred_at: datetime | None = None,
) -> int:
    """
    Record a cost-unit charge for the given entity into ResourceDailyLedger.

    Parameters:
        entity_scope: Logical scope for the entity (e.g., "user", "api_key").
        entity_value: Identifier within the scope (e.g., "123").
        tokens: Tokens consumed by the operation (for LLM calls).
        minutes: Minutes consumed (for audio or similar workloads).
        requests: Requests consumed (generic fallback).
        op_id: Optional idempotency key. When provided, repeated calls with the
            same op_id for the same day/entity/category are ignored by the
            ledger. When omitted, a best-effort op_id is derived from scope,
            value, and timestamp.
        occurred_at: Optional timestamp; defaults to now() in UTC.

    Returns:
        int: The computed cost units for this operation (0 when no units were
        recorded or when the ledger could not be initialized).
    """
    units = compute_cost_units(tokens=tokens, minutes=minutes, requests=requests)
    if units <= 0:
        return 0

    # Lazily initialize the shared ledger via the DAL; failures are logged but
    # never break callers.
    try:
        ledger = ResourceDailyLedger()  # type: ignore[call-arg]
        await ledger.initialize()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"CostUnits: failed to initialize ResourceDailyLedger: {exc}")
        return 0

    ts = occurred_at or datetime.now(timezone.utc)
    oid = op_id or f"cost-units:{entity_scope}:{entity_value}:{int(ts.timestamp())}"

    entry = LedgerEntry(  # type: ignore[call-arg]
        entity_scope=entity_scope,
        entity_value=str(entity_value),
        category="cost_units",
        units=int(units),
        op_id=str(oid),
        occurred_at=ts,
    )
    try:
        await ledger.add(entry)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"CostUnits: ledger.add failed for entity={entity_scope}:{entity_value}: {exc}")
        return 0
    return units


async def remaining_daily_cost_units(
    *,
    entity_scope: str,
    entity_value: str,
    daily_cap_units: int,
    day_utc: str | None = None,
) -> int:
    """
    Return remaining daily cost units for an entity given a daily cap.

    This is a thin wrapper over ResourceDailyLedger.remaining_for_day using
    the "cost_units" category.
    """
    if daily_cap_units <= 0:
        return 0

    try:
        ledger = ResourceDailyLedger()  # type: ignore[call-arg]
        await ledger.initialize()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"CostUnits: failed to initialize ledger in remaining_daily_cost_units: {exc}")
        return daily_cap_units

    try:
        remaining = await ledger.remaining_for_day(
            entity_scope=entity_scope,
            entity_value=str(entity_value),
            category="cost_units",
            daily_cap=int(daily_cap_units),
            day_utc=day_utc,
        )
        return int(remaining)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(
            f"CostUnits: remaining_for_day failed for entity={entity_scope}:{entity_value}: {exc}"
        )
        # Fail-open by returning the full cap so callers treat this as unlimited.
        return int(daily_cap_units)
