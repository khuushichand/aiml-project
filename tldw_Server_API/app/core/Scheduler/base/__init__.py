"""
Base abstractions for the scheduler system.
"""

from .exceptions import (
    BackendError,
    BufferClosedError,
    BufferError,
    BufferFlushError,
    ConfigurationError,
    ConnectionError,
    DuplicateTaskError,
    HandlerExecutionError,
    HandlerNotFoundError,
    LeaseConflictError,
    LeaseError,
    LeaseExpiredError,
    MigrationError,
    QueueEmptyError,
    QueueError,
    QueueFullError,
    SchedulerError,
    SchemaError,
    TaskCancelledError,
    TaskDependencyError,
    TaskError,
    TaskExpiredError,
    TaskNotFoundError,
    TaskTimeoutError,
    TransactionError,
    WorkerError,
    WorkerOverloadError,
    WorkerShutdownError,
)
from .queue_backend import QueueBackend
from .registry import TaskRegistry, get_registry, task
from .task import Task, TaskPriority, TaskStatus

__all__ = [
    # Task
    'Task',
    'TaskStatus',
    'TaskPriority',

    # Backend
    'QueueBackend',

    # Registry
    'TaskRegistry',
    'get_registry',
    'task',

    # Exceptions
    'SchedulerError',
    'QueueError',
    'TaskError',
    'BackendError',
    'QueueFullError',
    'QueueEmptyError',
    'DuplicateTaskError',
    'TaskNotFoundError',
    'TaskExpiredError',
    'TaskDependencyError',
    'TaskTimeoutError',
    'TaskCancelledError',
    'HandlerNotFoundError',
    'HandlerExecutionError',
    'ConnectionError',
    'TransactionError',
    'SchemaError',
    'MigrationError',
    'LeaseError',
    'LeaseExpiredError',
    'LeaseConflictError',
    'WorkerError',
    'WorkerShutdownError',
    'WorkerOverloadError',
    'ConfigurationError',
    'BufferError',
    'BufferClosedError',
    'BufferFlushError'
]
