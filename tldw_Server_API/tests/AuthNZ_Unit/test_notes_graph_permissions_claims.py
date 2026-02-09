from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import notes_graph as notes_graph_mod
from tldw_Server_API.app.core.AuthNZ.permissions import NOTES_GRAPH_READ, NOTES_GRAPH_WRITE
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


def _make_principal(
    *,
    kind: str = "user",
    is_admin: bool = False,
    roles: List[str] | None = None,
    permissions: List[str] | None = None,
) -> AuthPrincipal:
    return AuthPrincipal(
        kind=kind,
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=roles or [],
        permissions=permissions or [],
        is_admin=is_admin,
        org_ids=[],
        team_ids=[],
    )


def _build_app_with_overrides(
    principal: AuthPrincipal,
    *,
    user_permissions: List[str],
) -> FastAPI:
    app = FastAPI()
    app.include_router(notes_graph_mod.router, prefix="/api/v1/notes")

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        ip = request.client.host if getattr(request, "client", None) else None
        ua = request.headers.get("User-Agent") if getattr(request, "headers", None) else None
        request_id = request.headers.get("X-Request-ID") if getattr(request, "headers", None) else None
        request.state.auth = AuthContext(
            principal=principal,
            ip=ip,
            user_agent=ua,
            request_id=request_id,
        )
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal

    async def _fake_get_request_user():
        return SimpleNamespace(
            id=1,
            id_str="1",
            username="notes-user",
            is_active=True,
            roles=list(principal.roles),
            permissions=list(user_permissions),
            is_admin=principal.is_admin,
            tenant_id="default",
        )

    app.dependency_overrides[notes_graph_mod.get_request_user] = _fake_get_request_user

    async def _allow_non_authz_dep() -> None:
        # Claim tests isolate require_permissions behavior and bypass unrelated
        # per-route token-scope/rate-limit enforcement dependencies.
        return None

    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in getattr(dependant, "dependencies", []):
            call = getattr(dep, "call", None)
            if call is None:
                continue
            if getattr(call, "_tldw_token_scope", False):
                app.dependency_overrides[call] = _allow_non_authz_dep
            if getattr(call, "_tldw_rate_limit_resource", None) is not None:
                app.dependency_overrides[call] = _allow_non_authz_dep

    class _StubChaChaDB:
        def create_manual_note_edge(
            self,
            *,
            user_id: str,
            from_note_id: str,
            to_note_id: str,
            directed: bool,
            weight: float,
            metadata: object,
            created_by: str,
        ) -> Dict[str, Any]:
            return {
                "id": "edge:test",
                "user_id": user_id,
                "from_note_id": from_note_id,
                "to_note_id": to_note_id,
                "directed": directed,
                "weight": weight,
                "metadata": metadata,
                "created_by": created_by,
            }

        def delete_manual_note_edge(self, *, user_id: str, edge_id: str) -> bool:
            _ = (user_id, edge_id)
            return True

        # Graph query stubs needed by NoteGraphService
        def count_user_notes(self, include_deleted=True):
            return 0

        def get_all_note_ids_for_graph(self, include_deleted=True, limit=500):
            return []

        def get_notes_batch(self, note_ids, include_deleted=True):
            return []

        def get_manual_edges_for_notes(self, user_id, note_ids):
            return []

        def get_note_tag_edges(self, note_ids):
            return []

        def count_notes_per_tag(self):
            return {}

        def get_note_source_info(self, note_ids):
            return []

    async def _fake_get_chacha_db_for_user():
        return _StubChaChaDB()

    app.dependency_overrides[notes_graph_mod.get_chacha_db_for_user] = _fake_get_chacha_db_for_user

    return app


@pytest.mark.asyncio
async def test_notes_graph_read_forbidden_when_principal_lacks_permission_but_user_has():
    """
    User object advertises notes.graph.read, but the AuthPrincipal lacks
    NOTES_GRAPH_READ. require_permissions(NOTES_GRAPH_READ) must still
    forbid the request.
    """
    principal = _make_principal(
        roles=["user"],
        permissions=[],
        is_admin=False,
    )
    app = _build_app_with_overrides(
        principal,
        user_permissions=[NOTES_GRAPH_READ],
    )

    with TestClient(app) as client:
        resp = client.get("/api/v1/notes/graph")
    assert resp.status_code == 403
    assert NOTES_GRAPH_READ in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_notes_graph_read_allowed_when_principal_has_permission():
    principal = _make_principal(
        roles=["user"],
        permissions=[NOTES_GRAPH_READ],
        is_admin=False,
    )
    app = _build_app_with_overrides(
        principal,
        user_permissions=[NOTES_GRAPH_READ],
    )

    with TestClient(app) as client:
        resp = client.get("/api/v1/notes/graph")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("nodes"), list)
    assert isinstance(body.get("edges"), list)


@pytest.mark.asyncio
async def test_notes_graph_write_forbidden_when_principal_lacks_permission_but_user_has():
    """
    User object advertises notes.graph.write, but the AuthPrincipal lacks
    NOTES_GRAPH_WRITE. require_permissions(NOTES_GRAPH_WRITE) must still
    forbid the request.
    """
    principal = _make_principal(
        roles=["user"],
        permissions=[],
        is_admin=False,
    )
    app = _build_app_with_overrides(
        principal,
        user_permissions=[NOTES_GRAPH_WRITE],
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/notes/n-1/links",
            json={"to_note_id": "n-2"},
        )
    assert resp.status_code == 403
    assert NOTES_GRAPH_WRITE in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_notes_graph_write_allowed_when_principal_has_permission():
    principal = _make_principal(
        roles=["user"],
        permissions=[NOTES_GRAPH_WRITE],
        is_admin=False,
    )
    app = _build_app_with_overrides(
        principal,
        user_permissions=[NOTES_GRAPH_WRITE],
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/notes/n-1/links",
            json={"to_note_id": "n-2"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") in {"created", "stub"}
