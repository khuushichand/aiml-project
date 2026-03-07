import pytest

from tldw_Server_API.app.core.Research.models import ResearchPlan


pytestmark = pytest.mark.unit


def _plan(source_policy: str) -> ResearchPlan:
    return ResearchPlan(
        query="Compare internal notes with public sources",
        focus_areas=["evidence alignment"],
        source_policy=source_policy,
        autonomy_mode="checkpointed",
        stop_criteria={"min_cited_sections": 1},
    )


@pytest.mark.asyncio
async def test_broker_uses_only_local_lane_for_local_only_policy():
    from tldw_Server_API.app.core.Research.broker import ResearchBroker

    calls: list[str] = []

    async def local_lane(**kwargs):
        calls.append("local")
        return [
            {
                "id": "doc-1",
                "title": "Internal note",
                "content": "Internal note summary",
                "url": None,
            }
        ]

    async def academic_lane(**kwargs):
        calls.append("academic")
        return []

    async def web_lane(**kwargs):
        calls.append("web")
        return []

    broker = ResearchBroker(
        local_search_fn=local_lane,
        academic_search_fn=academic_lane,
        web_search_fn=web_lane,
    )

    result = await broker.collect_focus_area(
        session_id="rs_1",
        owner_user_id="1",
        focus_area="evidence alignment",
        plan=_plan("local_only"),
        context={},
    )

    assert calls == ["local"]
    assert len(result.sources) == 1
    assert result.sources[0].source_type == "local_document"
    assert result.evidence_notes[0].focus_area == "evidence alignment"


@pytest.mark.asyncio
async def test_broker_falls_back_to_external_lanes_when_local_first_is_sparse():
    from tldw_Server_API.app.core.Research.broker import ResearchBroker

    calls: list[str] = []

    async def local_lane(**kwargs):
        calls.append("local")
        return [{"id": "doc-1", "title": "Only local hit", "content": "one"}]

    async def academic_lane(**kwargs):
        calls.append("academic")
        return [{"doi": "10.1000/example", "title": "Academic source", "summary": "paper"}]

    async def web_lane(**kwargs):
        calls.append("web")
        return [{"url": "https://example.com/report", "title": "Web source", "snippet": "report"}]

    broker = ResearchBroker(
        local_search_fn=local_lane,
        academic_search_fn=academic_lane,
        web_search_fn=web_lane,
    )

    result = await broker.collect_focus_area(
        session_id="rs_1",
        owner_user_id="1",
        focus_area="evidence alignment",
        plan=_plan("local_first"),
        context={},
    )

    assert calls == ["local", "academic", "web"]
    assert {source.source_type for source in result.sources} == {
        "local_document",
        "academic_paper",
        "web_page",
    }
    assert result.collection_metrics["lane_counts"]["local"] == 1


@pytest.mark.asyncio
async def test_broker_dedupes_sources_across_lanes():
    from tldw_Server_API.app.core.Research.broker import ResearchBroker

    async def local_lane(**kwargs):
        return [{"url": "https://example.com/shared", "title": "Shared source", "content": "local"}]

    async def academic_lane(**kwargs):
        return []

    async def web_lane(**kwargs):
        return [{"url": "https://example.com/shared", "title": "Shared source", "snippet": "web"}]

    broker = ResearchBroker(
        local_search_fn=local_lane,
        academic_search_fn=academic_lane,
        web_search_fn=web_lane,
    )

    result = await broker.collect_focus_area(
        session_id="rs_1",
        owner_user_id="1",
        focus_area="evidence alignment",
        plan=_plan("balanced"),
        context={},
    )

    assert len(result.sources) == 1
    assert len(result.evidence_notes) == 1
    assert result.collection_metrics["deduped_sources"] == 1
