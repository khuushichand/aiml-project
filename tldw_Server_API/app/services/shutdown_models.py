from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Awaitable, Callable, Literal


class ShutdownPhase(StrEnum):
    TRANSITION = "transition"
    ACCEPTORS = "acceptors"
    PRODUCERS = "producers"
    WORKERS = "workers"
    RESOURCES = "resources"
    FINALIZERS = "finalizers"


class ShutdownPolicy(StrEnum):
    DEV_FAST = "dev_fast"
    PROD_DRAIN = "prod_drain"
    BEST_EFFORT = "best_effort"


ShutdownResult = Literal["stopped", "timed_out", "cancelled", "skipped", "failed"]


@dataclass(slots=True)
class ShutdownComponent:
    name: str
    phase: ShutdownPhase | str
    policy: ShutdownPolicy | str
    default_timeout_ms: int
    stop: Callable[[], Awaitable[None] | None]

    def __post_init__(self) -> None:
        if not isinstance(self.phase, ShutdownPhase):
            self.phase = ShutdownPhase(str(self.phase))
        if not isinstance(self.policy, ShutdownPolicy):
            self.policy = ShutdownPolicy(str(self.policy))
        self.default_timeout_ms = max(0, int(self.default_timeout_ms))


@dataclass(slots=True)
class ShutdownComponentSummary:
    name: str
    phase: ShutdownPhase
    policy: ShutdownPolicy
    result: ShutdownResult
    started_at: float
    finished_at: float
    duration_ms: int
    timeout_ms: int
    error: str | None = None


@dataclass(slots=True)
class ShutdownPhaseSummary:
    phase: ShutdownPhase
    started_at: float
    finished_at: float
    duration_ms: int
    budget_ms: int
    component_names: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ShutdownSummary:
    profile: str
    started_at: float
    finished_at: float
    deadline_at: float
    hard_cutoff_at: float
    wall_time_ms: int
    soft_overrun_used_ms: int
    idempotent: bool = False
    components: dict[str, ShutdownComponentSummary] = field(default_factory=dict)
    phases: dict[ShutdownPhase, ShutdownPhaseSummary] = field(default_factory=dict)
