from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_list_data_subject_requests_passes_org_scope_to_repo(monkeypatch) -> None:
    from tldw_Server_API.app.services import admin_data_subject_requests_service as service

    principal = SimpleNamespace(user_id=17, roles=["admin"])

    class _StubRepo:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def ensure_schema(self) -> None:
            return None

        async def list_requests(
            self,
            *,
            limit: int,
            offset: int,
            org_ids: list[int] | None = None,
            resolved_user_ids: list[int] | None = None,
        ):
            self.calls.append(
                {
                    "limit": limit,
                    "offset": offset,
                    "org_ids": list(org_ids or []),
                    "resolved_user_ids": list(resolved_user_ids or []),
                }
            )
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
            ], 1

    stub_repo = _StubRepo()

    monkeypatch.setattr(service.admin_scope_service, "is_platform_admin", lambda current_principal: False)

    async def _fake_get_admin_org_ids(current_principal):
        assert current_principal is principal
        return [99]

    monkeypatch.setattr(service.admin_scope_service, "get_admin_org_ids", _fake_get_admin_org_ids)

    items, total = await service.list_data_subject_requests(
        principal,
        limit=50,
        offset=0,
        requests_repo=stub_repo,
    )

    assert total == 1
    assert len(items) == 1
    assert stub_repo.calls == [
        {
            "limit": 50,
            "offset": 0,
            "org_ids": [99],
            "resolved_user_ids": [],
        }
    ]
