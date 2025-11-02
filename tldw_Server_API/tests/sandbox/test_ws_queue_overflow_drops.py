from __future__ import annotations

import asyncio
import os
from typing import Dict, Any, List

import pytest

from tldw_Server_API.app.core.Sandbox.streams import RunStreamHub
from tldw_Server_API.app.core.Metrics import get_metrics_registry


@pytest.mark.unit
def test_ws_queue_overflow_drops_and_metrics() -> None:
    # Use a fresh hub to avoid cross-test state
    hub = RunStreamHub()

    # Create a small queue (maxsize=5) to force overflows
    q: asyncio.Queue = asyncio.Queue(maxsize=5)

    # Push more than capacity to trigger drop_oldest path
    for i in range(12):
        hub._queue_put_nowait(q, {"type": "stdout", "seq": i})  # type: ignore[attr-defined]

    # Drain queue and ensure only the most recent 5 remain
    drained: List[Dict[str, Any]] = []
    while True:
        try:
            drained.append(q.get_nowait())
        except Exception:
            break

    assert len(drained) == 5
    # Oldest in queue should be >= 7 (we inserted 0..11)
    min_seq = min(int(f.get("seq", -1)) for f in drained)
    assert min_seq >= 7

    # Verify that the metrics counter for queue drops has been incremented
    reg = get_metrics_registry()
    vals = reg.values.get("sandbox_ws_queue_drops_total")
    # There should be at least one increment recorded
    assert vals and sum(v.value for v in vals) >= 1
