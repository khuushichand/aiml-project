# job_types.py
# Shared job type/status enums for Prompt Studio (core Jobs era)

from enum import Enum


class JobType(str, Enum):
    EVALUATION = "evaluation"
    OPTIMIZATION = "optimization"
    GENERATION = "generation"


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


__all__ = ["JobType", "JobStatus"]
