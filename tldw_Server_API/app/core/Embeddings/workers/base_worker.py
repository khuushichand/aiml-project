"""Base worker helpers for embeddings pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from prometheus_client import Histogram, REGISTRY


def _get_or_create_histogram(name: str, description: str, labelnames: Iterable[str]) -> Histogram:
    """Return a Histogram with the requested name, reusing existing collectors when possible."""
    existing = REGISTRY._names_to_collectors.get(name)
    if existing is not None:
        if hasattr(existing, "_labelnames") and set(existing._labelnames) == set(labelnames):
            return existing  # type: ignore[return-value]
        REGISTRY.unregister(existing)
    return Histogram(name, description, labelnames)


EMBEDDING_STAGE_BATCH_SIZE = _get_or_create_histogram(
    "embedding_stage_batch_size",
    "Batch size per embeddings stage",
    ["stage"],
)
EMBEDDING_STAGE_PAYLOAD_BYTES = _get_or_create_histogram(
    "embedding_stage_payload_bytes",
    "Payload size per embeddings stage",
    ["stage"],
)

for _stage in ("chunking", "embedding", "storage"):
    EMBEDDING_STAGE_BATCH_SIZE.labels(stage=_stage).observe(0)
    EMBEDDING_STAGE_PAYLOAD_BYTES.labels(stage=_stage).observe(0)


@dataclass
class WorkerConfig:
    worker_id: str
    worker_type: str
    queue_name: str
    consumer_group: str


class BaseWorker:
    """Minimal base worker for embeddings pipeline steps."""

    def __init__(self, config: WorkerConfig) -> None:
        self.config = config

    def observe_batch(self, stage: str, batch_size: int, payload_bytes: Optional[int] = None) -> None:
        """Record batch metrics for observability."""
        EMBEDDING_STAGE_BATCH_SIZE.labels(stage=stage).observe(batch_size)
        if payload_bytes is not None:
            EMBEDDING_STAGE_PAYLOAD_BYTES.labels(stage=stage).observe(payload_bytes)
