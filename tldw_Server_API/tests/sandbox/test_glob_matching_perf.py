from __future__ import annotations

import time
import fnmatch

import pytest


@pytest.mark.unit
def test_glob_matching_perf_on_large_set() -> None:
    # Simulate docker_runner capture filtering logic with many files and a few patterns
    files = []
    for i in range(500):
        files.append(f"logs/run_{i}.log")
        files.append(f"out/part_{i}.txt")
        files.append(f"tmp/{i}.bin")
    patterns = ["**/*.log", "out/*.txt", "*.md"]

    t0 = time.perf_counter()
    matched = [p for p in files if any(fnmatch.fnmatchcase(p, pat) for pat in patterns)]
    dt = time.perf_counter() - t0

    # Sanity: expect some matches (out/*.txt and **/*.log)
    assert len(matched) > 0
    # Should be very fast even on modest hardware
    assert dt < 0.5, f"glob matching too slow: {dt:.3f}s over {len(files)} files"

