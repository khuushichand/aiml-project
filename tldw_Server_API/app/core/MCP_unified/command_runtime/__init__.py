"""Virtual CLI command runtime for MCP Unified."""

from .executor import CommandBackend, CommandRuntimeExecutor
from .models import CommandChain, CommandInvocation, Pipeline
from .models import CommandExecutionResult, CommandExecutionStep, CommandSpillReference, CommandStepResult
from .presentation import present_command_execution_result
from .parser import parse_command
from .registry import CommandDescriptor, CommandRegistry, build_default_registry

__all__ = [
    "CommandBackend",
    "CommandChain",
    "CommandDescriptor",
    "CommandExecutionResult",
    "CommandExecutionStep",
    "CommandInvocation",
    "CommandRegistry",
    "CommandRuntimeExecutor",
    "Pipeline",
    "CommandSpillReference",
    "CommandStepResult",
    "build_default_registry",
    "parse_command",
    "present_command_execution_result",
]
