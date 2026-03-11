from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_list_data_subject_requests_pages_all_scoped_users(monkeypatch) -> None:
    from tldw_Server_API.app.services import admin_data_subject_requests_service as service

    principal = SimpleNamespace(user_id=17, roles=["admin"])

    class _StubRepo:
        async def ensure_schema(self) -> None:
            return None

        async def list_requests(self, *, limit: int, offset: int, resolved_user_ids: list[int] | None = None):
            return [
                {
                    "id": 1,
                    "client_request_id": "dsr-1",
                    "requester_identifier": "subject@example.com",
                    "resolved_user_id": 1005,
                    "request_type": "access",
                    "status": "recorded",
                    "selected_categories": ["media_records"],
                    "preview_summary": [],
                    "coverage_metadata": {},
                    "requested_by_user_id": 17,
                    "requested_at": "2026-03-10T12:00:00+00:00",
                    "notes": None,
                }
            ], len(resolved_user_ids or [])

    class _StubUsersRepo:
        def __init__(self) -> None:
            self.calls: list[tuple[int, int, tuple[int, ...]]] = []

        async def list_users(self, *, offset: int, limit: int, org_ids: list[int] | None = None, **kwargs):
            del kwargs
            self.calls.append((offset, limit, tuple(org_ids or [])))
            user_ids = list(range(1, 1051))
            page = user_ids[offset: offset + limit]
            return [{"id": user_id} for user_id in page], len(user_ids)

    stub_users_repo = _StubUsersRepo()

    async def _fake_get_db_pool():
        return object()

    @classmethod
    async def _fake_from_pool(cls):
        del cls
        return stub_users_repo

    monkeypatch.setattr(service, "get_db_pool", _fake_get_db_pool)
    monkeypatch.setattr(service, "AuthnzDataSubjectRequestsRepo", lambda db_pool: _StubRepo())
    monkeypatch.setattr(service.admin_scope_service, "is_platform_admin", lambda current_principal: False)

    async def _fake_get_admin_org_ids(current_principal):
        assert current_principal is principal
        return [99]

    monkeypatch.setattr(service.admin_scope_service, "get_admin_org_ids", _fake_get_admin_org_ids)

    from tldw_Server_API.app.core.AuthNZ.repos import users_repo as users_repo_mod

    monkeypatch.setattr(users_repo_mod.AuthnzUsersRepo, "from_pool", _fake_from_pool)

    items, total = await service.list_data_subject_requests(
        principal,
        limit=50,
        offset=0,
    )

    assert total == 1050
    assert len(items) == 1
    assert stub_users_repo.calls == [
        (0, 1000, (99,)),
        (1000, 1000, (99,)),
    ]
