from __future__ import annotations

from typing import Iterable

from tldw_Server_API.app.api.v1.router_groups.spec import RouterSpec


def iter_core_router_specs() -> Iterable[RouterSpec]:
    """Yield core/always-on router specs.

    This is intentionally empty in the first extraction step and will be
    populated incrementally as route registration migrates out of main.py.
    """
    return ()
