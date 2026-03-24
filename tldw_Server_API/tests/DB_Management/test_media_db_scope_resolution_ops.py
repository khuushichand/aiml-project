import importlib
import importlib.util
from types import SimpleNamespace

import pytest


pytestmark = pytest.mark.unit


def _load_scope_resolution_ops_module():
    module_name = "tldw_Server_API.app.core.DB_Management.media_db.runtime.scope_resolution_ops"
    spec = importlib.util.find_spec(module_name)
    assert spec is not None, f"Expected runtime module spec for {module_name}"
    return importlib.import_module(module_name)


def test_resolve_scope_ids_rebinds_on_media_database() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.media_database import MediaDatabase

    scope_resolution_ops_module = _load_scope_resolution_ops_module()

    assert MediaDatabase.__dict__["_resolve_scope_ids"].__globals__["__name__"] == (
        scope_resolution_ops_module.__name__
    )


def test_resolve_scope_ids_uses_defaults_and_updates_scope_cache(monkeypatch) -> None:
    scope_resolution_ops_module = _load_scope_resolution_ops_module()
    db = SimpleNamespace(default_org_id=10, default_team_id=20, _scope_cache=None)

    monkeypatch.setattr(scope_resolution_ops_module, "get_scope", lambda: None)

    assert scope_resolution_ops_module._resolve_scope_ids(db) == (10, 20)
    assert db._scope_cache == (10, 20)


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        (SimpleNamespace(effective_org_id=30, effective_team_id=40), (30, 40)),
        (SimpleNamespace(effective_org_id=30, effective_team_id=None), (30, 20)),
        (SimpleNamespace(effective_org_id=None, effective_team_id=40), (10, 40)),
    ],
)
def test_resolve_scope_ids_applies_scope_overrides_with_partial_default_fallback(
    monkeypatch,
    scope,
    expected: tuple[int | None, int | None],
) -> None:
    scope_resolution_ops_module = _load_scope_resolution_ops_module()
    db = SimpleNamespace(default_org_id=10, default_team_id=20, _scope_cache=None)

    monkeypatch.setattr(scope_resolution_ops_module, "get_scope", lambda: scope)

    assert scope_resolution_ops_module._resolve_scope_ids(db) == expected
    assert db._scope_cache == expected


def test_resolve_scope_ids_falls_back_when_get_scope_raises_noncritical_exception(
    monkeypatch,
) -> None:
    scope_resolution_ops_module = _load_scope_resolution_ops_module()
    db = SimpleNamespace(default_org_id=10, default_team_id=20, _scope_cache=None)

    def raise_scope_error():
        raise RuntimeError("scope unavailable")

    monkeypatch.setattr(scope_resolution_ops_module, "get_scope", raise_scope_error)

    assert scope_resolution_ops_module._resolve_scope_ids(db) == (10, 20)
    assert db._scope_cache == (10, 20)
