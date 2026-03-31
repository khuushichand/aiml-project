"""Data models for the virtual CLI command runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CommandInvocation:
    """A single command invocation with argv-style arguments."""

    argv: list[str]


@dataclass(frozen=True, slots=True)
class Pipeline:
    """A pipeline of commands joined by the `|` operator."""

    commands: list[CommandInvocation] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CommandChain:
    """A chain of one or more pipelines linked by shell-style operators."""

    segments: list[Pipeline] = field(default_factory=list)
    links: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CommandSpillReference:
    """Reference to content spilled to disk after exceeding an in-memory cap."""

    path: str
    bytes_written: int
    line_count: int = 0
    preview: str = ""
    encoding: str = "utf-8"

    def read_text(self) -> str:
        """Recover the original UTF-8 text payload from the spill file."""

        return Path(self.path).read_text(encoding=self.encoding)


@dataclass(frozen=True, slots=True)
class CommandStepResult:
    """Raw result from a single backend command execution."""

    stdout: str | bytes = ""
    stderr: str | bytes = ""
    exit_code: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CommandExecutionStep:
    """Trace entry for a command executed by the raw runtime."""

    argv: list[str]
    stdin: Any = ""
    stdout: str | bytes = ""
    stderr: str | bytes = ""
    exit_code: int = 0
    duration_ms: float = 0.0
    stdout_spill: CommandSpillReference | None = None
    stderr_spill: CommandSpillReference | None = None
    stdout_is_binary: bool = False
    stderr_is_binary: bool = False
    stderr_contains_binary: bool = False


@dataclass(frozen=True, slots=True)
class CommandExecutionResult:
    """Aggregate raw command-chain execution output."""

    stdout: str | bytes = ""
    stderr: str | bytes = ""
    exit_code: int = 0
    duration_ms: float = 0.0
    steps: list[CommandExecutionStep] = field(default_factory=list)
    stdout_spill: CommandSpillReference | None = None
    stderr_spill: CommandSpillReference | None = None
    stderr_spills: list[CommandSpillReference] = field(default_factory=list)
    stdout_is_binary: bool = False
    stderr_is_binary: bool = False
    stderr_contains_binary: bool = False
