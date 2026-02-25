import pytest

from tldw_Server_API.app.core.Governance.store import GovernanceStore

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_open_gap_upsert_deduplicates_same_fingerprint(tmp_path):
    db_path = tmp_path / "gov_gaps.db"
    store = GovernanceStore(sqlite_path=str(db_path))
    await store.ensure_schema()

    first = await store.upsert_open_gap(
        question="Which HTTP client should we use?",
        category="dependencies",
        org_id=7,
        team_id=11,
    )
    second = await store.upsert_open_gap(
        question=" Which HTTP client should we use?  ",  # normalized same question
        category="dependencies",
        org_id=7,
        team_id=11,
    )

    assert first.id == second.id
    assert first.question_fingerprint == second.question_fingerprint
    assert first.status == "open"


@pytest.mark.asyncio
async def test_open_gap_upsert_distinct_scope_creates_new_gap(tmp_path):
    db_path = tmp_path / "gov_gaps_scope.db"
    store = GovernanceStore(sqlite_path=str(db_path))
    await store.ensure_schema()

    team_a = await store.upsert_open_gap(
        question="How should errors be handled?",
        category="error_handling",
        org_id=7,
        team_id=101,
    )
    team_b = await store.upsert_open_gap(
        question="How should errors be handled?",
        category="error_handling",
        org_id=7,
        team_id=202,
    )

    assert team_a.id != team_b.id

