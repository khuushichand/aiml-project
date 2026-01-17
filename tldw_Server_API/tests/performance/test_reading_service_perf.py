import os
import time

import pytest

from tldw_Server_API.app.core.Collections.reading_service import _contains_html_tag


pytestmark = pytest.mark.performance


def _perf_enabled() -> bool:
    return os.getenv("PERF", "0").lower() in {"1", "true", "yes", "on"}


pytestmark = pytest.mark.skipif(not _perf_enabled(), reason="set PERF=1 to run performance checks")


def test_contains_html_tag_linear_scan():
    sizes = [1000, 4000, 16000]
    target_total = int(os.getenv("PERF_HTML_TAG_CHARS", "2000000"))
    per_char_times = []
    for size in sizes:
        iters = max(1, target_total // size)
        sample = "<A" * size
        t0 = time.perf_counter()
        for _ in range(iters):
            _contains_html_tag(sample)
        dt = time.perf_counter() - t0
        per_char = dt / (size * iters)
        per_char_times.append(per_char)
        print(
            f"html_tag_detect size={size} iters={iters} dt={dt:.6f}s per_char={per_char:.3e}"
        )
    ratio = max(per_char_times) / min(per_char_times)
    assert ratio < 10.0
