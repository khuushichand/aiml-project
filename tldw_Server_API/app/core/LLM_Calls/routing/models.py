"""Core routing models shared across LLM surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

RoutingStrategy = Literal["llm_router", "rules_router"]
RoutingFallbackStrategy = Literal["rules_router"]
RoutingObjective = Literal["highest_quality", "lowest_cost", "lowest_latency", "balanced"]
RoutingMode = Literal["per_turn", "sticky_session"]
RoutingBoundaryMode = Literal["server_default_provider", "pinned_provider", "cross_provider"]
RoutingFailureMode = Literal["fallback_then_error", "error"]


class RoutingOverride(BaseModel):
    """Optional request-time overrides for server-side model routing."""

    model_config = ConfigDict(extra="forbid")

    strategy: Optional[RoutingStrategy] = Field(
        default=None,
        description="Preferred router strategy when model='auto'.",
    )
    objective: Optional[RoutingObjective] = Field(
        default=None,
        description="Optimization objective for server-side routing.",
    )
    mode: Optional[RoutingMode] = Field(
        default=None,
        description="Whether routing is re-evaluated each turn or reused for a sticky scope.",
    )
    cross_provider: Optional[bool] = Field(
        default=None,
        description="Allow the router to choose outside the pinned/default provider boundary.",
    )
    failure_mode: Optional[RoutingFailureMode] = Field(
        default=None,
        description="Whether the request should error immediately after routing failure.",
    )


@dataclass(frozen=True)
class RoutingPolicy:
    """Resolved policy values after applying defaults and request overrides."""

    request_model: str
    server_default_provider: str
    boundary_mode: RoutingBoundaryMode
    pinned_provider: Optional[str] = None
    strategy: RoutingStrategy = "llm_router"
    fallback_strategy: RoutingFallbackStrategy = "rules_router"
    objective: RoutingObjective = "highest_quality"
    mode: RoutingMode = "per_turn"
    cross_provider: bool = False
    failure_mode: RoutingFailureMode = "fallback_then_error"


@dataclass(frozen=True)
class RouterRequest:
    """Normalized request context passed into the router service."""

    model: str
    surface: str
    latest_user_turn: str | None = None
    scope: str | None = None
    requested_capabilities: dict[str, Any] = field(default_factory=dict)
    routing_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoutingDecision:
    """Concrete provider/model pair chosen by the router."""

    provider: str
    model: str
    canonical: bool = True
    decision_source: str = "router"
    metadata: dict[str, Any] = field(default_factory=dict)
