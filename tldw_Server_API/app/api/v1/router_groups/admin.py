from __future__ import annotations

from typing import Iterable

from tldw_Server_API.app.api.v1.router_groups.spec import RouterSpec


def iter_admin_router_specs() -> Iterable[RouterSpec]:
    """Yield admin/ops router specs.

    Populated incrementally as registration moves out of main.py.
    """
    return ()

