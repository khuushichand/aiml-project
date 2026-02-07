from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from tldw_Server_API.app.core.testing import is_truthy


def _as_optional_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        parsed = int(value)
        return parsed if parsed > 0 else None
    except Exception:
        return None


def _as_optional_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        parsed = float(value)
        return parsed if parsed > 0 else None
    except Exception:
        return None


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return is_truthy(str(value).strip().lower())


def estimate_claims_tokens(text: str) -> int:
    """Estimate tokens using a simple 4-char heuristic."""
    if not text:
        return 0
    return max(1, int(len(text) / 4))


@dataclass
class ClaimsJobContext:
    user_id: int | None = None
    api_key_id: int | None = None
    request_id: str | None = None
    endpoint: str | None = None


@dataclass
class ClaimsJobBudget:
    max_cost_usd: float | None = None
    max_tokens: int | None = None
    strict: bool = False
    used_cost_usd: float = 0.0
    used_tokens: int = 0
    exhausted: bool = False
    exhausted_reason: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def _normalize(self) -> None:
        if self.max_cost_usd is not None and self.max_cost_usd <= 0:
            self.max_cost_usd = None
        if self.max_tokens is not None and self.max_tokens <= 0:
            self.max_tokens = None

    def reserve(self, *, cost_usd: float | None = None, tokens: int | None = None) -> bool:
        cost_val = max(0.0, float(cost_usd or 0.0))
        token_val = max(0, int(tokens or 0))
        if cost_val <= 0 and token_val <= 0:
            return True
        self._normalize()
        with self._lock:
            next_cost = self.used_cost_usd + cost_val
            next_tokens = self.used_tokens + token_val
            if self.max_cost_usd is not None and next_cost > self.max_cost_usd:
                self.exhausted = True
                self.exhausted_reason = "cost_usd"
                return False
            if self.max_tokens is not None and next_tokens > self.max_tokens:
                self.exhausted = True
                self.exhausted_reason = "tokens"
                return False
            self.used_cost_usd = next_cost
            self.used_tokens = next_tokens
            return True

    def add_usage(self, *, cost_usd: float | None = None, tokens: int | None = None) -> None:
        cost_val = max(0.0, float(cost_usd or 0.0))
        token_val = max(0, int(tokens or 0))
        if cost_val <= 0 and token_val <= 0:
            return
        with self._lock:
            self.used_cost_usd += cost_val
            self.used_tokens += token_val

    def remaining_cost_usd(self) -> float | None:
        self._normalize()
        if self.max_cost_usd is None:
            return None
        return max(0.0, float(self.max_cost_usd) - float(self.used_cost_usd))

    def remaining_tokens(self) -> int | None:
        self._normalize()
        if self.max_tokens is None:
            return None
        return max(0, int(self.max_tokens) - int(self.used_tokens))

    def remaining_ratio(self) -> float | None:
        ratios = []
        cost_remain = self.remaining_cost_usd()
        if cost_remain is not None and self.max_cost_usd:
            ratios.append(cost_remain / float(self.max_cost_usd))
        token_remain = self.remaining_tokens()
        if token_remain is not None and self.max_tokens:
            ratios.append(float(token_remain) / float(self.max_tokens))
        if not ratios:
            return None
        return min(ratios)

    def snapshot(self) -> dict[str, Any]:
        return {
            "max_cost_usd": self.max_cost_usd,
            "max_tokens": self.max_tokens,
            "used_cost_usd": round(float(self.used_cost_usd), 6),
            "used_tokens": int(self.used_tokens),
            "remaining_cost_usd": self.remaining_cost_usd(),
            "remaining_tokens": self.remaining_tokens(),
            "remaining_ratio": self.remaining_ratio(),
            "exhausted": bool(self.exhausted),
            "exhausted_reason": self.exhausted_reason,
        }


def resolve_claims_job_budget(
    *,
    settings: dict[str, Any] | None = None,
    max_cost_usd: float | None = None,
    max_tokens: int | None = None,
    strict: bool | None = None,
) -> ClaimsJobBudget | None:
    cfg = settings or {}
    enabled = _as_bool(cfg.get("CLAIMS_JOB_BUDGET_ENABLED"), False)
    if not enabled and max_cost_usd is None and max_tokens is None:
        return None
    cost = max_cost_usd if max_cost_usd is not None else (
        _as_optional_float(cfg.get("CLAIMS_JOB_MAX_COST_USD")) if enabled else None
    )
    tokens = max_tokens if max_tokens is not None else (
        _as_optional_int(cfg.get("CLAIMS_JOB_MAX_TOKENS")) if enabled else None
    )
    if cost is None and tokens is None:
        return None
    strict_flag = strict if strict is not None else _as_bool(cfg.get("CLAIMS_JOB_BUDGET_STRICT"), False)
    budget = ClaimsJobBudget(max_cost_usd=cost, max_tokens=tokens, strict=strict_flag)
    budget._normalize()
    return budget
