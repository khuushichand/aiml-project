from __future__ import annotations

"""
Lightweight orchestration helpers for process-only media endpoints.

This module is the Stage 3 entry point for wiring together:
  - input sourcing (uploads/URLs via input_sourcing),
  - type-specific processing libraries (PDF, code, audio, etc.),
  - result normalization helpers.

The initial version keeps the surface area intentionally small so existing
endpoints can migrate incrementally without changing their HTTP contracts.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .result_normalization import normalize_process_batch


@dataclass
class ProcessItem:
    """
    Minimal representation of an item to be processed by a process-* endpoint.

    Future iterations can extend this with richer metadata without affecting
    the HTTP-layer handlers.
    """

    input_ref: str
    local_path: Path
    media_type: str
    metadata: Dict[str, Any]


BatchProcessor = Callable[[List[ProcessItem]], Awaitable[List[Dict[str, Any]]]]


async def run_batch_processor(
    items: List[ProcessItem],
    processor: BatchProcessor,
    *,
    base_batch: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Execute a type-specific batch processor and wrap the results in a standard batch.

    Args:
        items: Inputs to process (already resolved to local paths).
        processor: Coroutine that turns items into per-input result dicts.
        base_batch: Optional pre-populated batch dict to extend (e.g., with
            pre-counted upload validation errors).

    Returns:
        A batch dict compatible with existing process-* responses, with
        `results`, `processed_count`, `errors_count`, and `errors`.
    """
    batch: Dict[str, Any] = base_batch.copy() if base_batch is not None else {}
    results = await processor(items)
    batch_results = list(batch.get("results") or [])
    batch_results.extend(results)
    batch["results"] = batch_results

    # Compute counts in the same way current endpoints do:
    # - "Success" items contribute to processed_count
    # - "Error" items contribute to errors_count
    # - "Warning" items are surfaced in results but do not increment counts.
    processed_count = sum(
        1
        for r in batch_results
        if str(r.get("status", "")).lower() == "success"
    )
    errors_count = sum(
        1 for r in batch_results if str(r.get("status", "")).lower() == "error"
    )
    batch.setdefault("errors", [])
    batch["processed_count"] = processed_count
    batch["errors_count"] = errors_count

    return normalize_process_batch(batch)


__all__ = ["ProcessItem", "run_batch_processor"]
