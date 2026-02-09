from __future__ import annotations

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.user_provider_secrets_repo import (
    AuthnzUserProviderSecretsRepo,
)


class _RowLike:
    def __init__(self, data: dict[str, object]) -> None:
        self._data = dict(data)

    def keys(self):
        return list(self._data.keys())

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        # Mimic sqlite3.Row iteration-by-values to guard against regression.
        return iter(self._data.values())


class _FakePool:
    pool = None

    async def fetchall(self, *_args, **_kwargs):
        return [
            _RowLike(
                {
                    "id": 1,
                    "user_id": 7,
                    "provider": "openai",
                    "key_hint": "1234",
                }
            )
        ]


@pytest.mark.asyncio
async def test_list_secrets_for_user_normalizes_row_like_objects() -> None:
    repo = AuthnzUserProviderSecretsRepo(db_pool=_FakePool())  # type: ignore[arg-type]
    rows = await repo.list_secrets_for_user(user_id=7)
    assert rows == [
        {
            "id": 1,
            "user_id": 7,
            "provider": "openai",
            "key_hint": "1234",
        }
    ]
