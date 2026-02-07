from __future__ import annotations

import pytest


pytestmark = pytest.mark.unit


def test_watchlists_perf_markers_registered(pytestconfig):
    markers = "\n".join(pytestconfig.getini("markers"))
    assert "performance" in markers
    assert "load" in markers
