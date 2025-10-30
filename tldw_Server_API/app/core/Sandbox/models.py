from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional
import hashlib


class RuntimeType(str, Enum):
    docker = "docker"
    firecracker = "firecracker"


@dataclass
class SessionSpec:
    runtime: Optional[RuntimeType] = None
    base_image: Optional[str] = None
    cpu_limit: Optional[float] = None
    memory_mb: Optional[int] = None
    timeout_sec: int = 300
    network_policy: str = "deny_all"
    env: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class Session:
    id: str
    runtime: RuntimeType
    base_image: Optional[str]
    expires_at: Optional[datetime]


@dataclass
class RunSpec:
    session_id: Optional[str]
    runtime: Optional[RuntimeType]
    base_image: Optional[str]
    command: List[str]
    env: Dict[str, str] = field(default_factory=dict)
    startup_timeout_sec: Optional[int] = None
    timeout_sec: int = 300
    cpu: Optional[float] = None
    memory_mb: Optional[int] = None
    network_policy: Optional[str] = None
    files_inline: List[tuple[str, bytes]] = field(default_factory=list)
    capture_patterns: List[str] = field(default_factory=list)


class RunPhase(str, Enum):
    queued = "queued"
    starting = "starting"
    running = "running"
    completed = "completed"
    failed = "failed"
    killed = "killed"
    timed_out = "timed_out"


@dataclass
class RunStatus:
    id: str
    phase: RunPhase
    spec_version: Optional[str] = None
    runtime: Optional[RuntimeType] = None
    base_image: Optional[str] = None
    image_digest: Optional[str] = None
    policy_hash: Optional[str] = None
    exit_code: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    message: Optional[str] = None
    resource_usage: Optional[Dict[str, int]] = None
    artifacts: Optional[Dict[str, bytes]] = None
    estimated_start_time: Optional[datetime] = None
