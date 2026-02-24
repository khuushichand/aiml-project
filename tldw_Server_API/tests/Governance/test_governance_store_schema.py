import pytest

from tldw_Server_API.app.core.Governance.store import GovernanceStore

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_ensure_schema_creates_required_tables(tmp_path):
    db_path = tmp_path / "gov_schema.db"
    store = GovernanceStore(sqlite_path=str(db_path))

    await store.ensure_schema()

    assert await store.table_exists("governance_rules")
    assert await store.table_exists("governance_gaps")

