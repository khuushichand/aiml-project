from __future__ import annotations

from typing import Any, Optional

import pytest

_BANNED_PREFIXES = ("requests", "httpx", "aiohttp")


def _format_target(target: Any, name: Optional[str]) -> str:
    if isinstance(target, str):
        return target
    module = getattr(target, "__module__", "") or ""
    obj_name = getattr(target, "__name__", "") or ""
    if module and obj_name:
        base = f"{module}.{obj_name}"
    elif module:
        base = module
    elif obj_name:
        base = obj_name
    else:
        base = repr(target)
    if name:
        return f"{base}.{name}"
    return base


def _is_banned_target(target_ref: str) -> bool:
    for prefix in _BANNED_PREFIXES:
        if target_ref == prefix or target_ref.startswith(f"{prefix}."):
            return True
    return False


@pytest.fixture(autouse=True)
def _guard_http_client_patching(monkeypatch: pytest.MonkeyPatch):
    original_setattr = monkeypatch.setattr
    original_setitem = monkeypatch.setitem

    def guarded_setattr(*args: Any, **kwargs: Any) -> Any:
        if args:
            target = args[0]
            name = None
            if not isinstance(target, str):
                if len(args) > 1 and isinstance(args[1], str):
                    name = args[1]
                elif isinstance(kwargs.get("name"), str):
                    name = kwargs.get("name")
            target_ref = _format_target(target, name)
            if _is_banned_target(target_ref):
                pytest.fail(
                    "Direct monkeypatching of requests/httpx/aiohttp is disallowed. "
                    "Patch tldw_Server_API.app.core.http_client helpers instead.",
                    pytrace=False,
                )
        return original_setattr(*args, **kwargs)

    def guarded_setitem(mapping: Any, name: Any, value: Any) -> Any:
        if isinstance(name, str) and _is_banned_target(name):
            pytest.fail(
                "Direct monkeypatching of requests/httpx/aiohttp is disallowed. "
                "Patch tldw_Server_API.app.core.http_client helpers instead.",
                pytrace=False,
            )
        return original_setitem(mapping, name, value)

    monkeypatch.setattr = guarded_setattr  # type: ignore[assignment]
    monkeypatch.setitem = guarded_setitem  # type: ignore[assignment]
    yield
    monkeypatch.setattr = original_setattr  # type: ignore[assignment]
    monkeypatch.setitem = original_setitem  # type: ignore[assignment]
