import pytest

from tldw_Server_API.app.core.AuthNZ.repos.api_keys_repo import AuthnzApiKeysRepo


pytestmark = pytest.mark.unit


class _StrictSqlitePool:
    def __init__(self, *, api_keys_columns: set[str], audit_columns: set[str], sqlite_fs_path: str = "/tmp/strict.db"):
        self.pool = None
        self._sqlite_fs_path = sqlite_fs_path
        self._api_keys_columns = api_keys_columns
        self._audit_columns = audit_columns

    async def fetchone(self, query: str, *args):  # noqa: ANN001, ANN002
        lowered = query.lower()
        if "name='api_keys'" in lowered or "name = 'api_keys'" in lowered:
            return {"name": "api_keys"}
        if "name='api_key_audit_log'" in lowered or "name = 'api_key_audit_log'" in lowered:
            return {"name": "api_key_audit_log"}
        return None

    async def fetchall(self, query: str, *args):  # noqa: ANN001, ANN002
        lowered = query.lower()
        if "pragma table_info(api_keys)" in lowered:
            return [(index, name) for index, name in enumerate(sorted(self._api_keys_columns))]
        if "pragma table_info(api_key_audit_log)" in lowered:
            return [(index, name) for index, name in enumerate(sorted(self._audit_columns))]
        return []


@pytest.mark.asyncio
async def test_api_keys_repo_ensure_tables_raises_on_missing_scope_column_in_strict_mode(monkeypatch):
    pool = _StrictSqlitePool(
        api_keys_columns={"id", "user_id", "key_hash"},
        audit_columns={"id", "api_key_id", "action", "created_at"},
    )
    repo = AuthnzApiKeysRepo(pool)

    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.repos.api_keys_repo.should_enforce_sqlite_schema_strictness",
        lambda _path: True,
    )

    with pytest.raises(RuntimeError, match="scope"):
        await repo.ensure_tables()


@pytest.mark.asyncio
async def test_api_keys_repo_ensure_tables_allows_missing_scope_when_shared_gate_is_off(monkeypatch):
    pool = _StrictSqlitePool(
        api_keys_columns={"id", "user_id", "key_hash"},
        audit_columns={"id", "api_key_id", "action", "created_at"},
    )
    repo = AuthnzApiKeysRepo(pool)

    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.repos.api_keys_repo.should_enforce_sqlite_schema_strictness",
        lambda _path: False,
    )

    await repo.ensure_tables()
