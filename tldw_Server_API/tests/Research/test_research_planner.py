import pytest


pytestmark = pytest.mark.unit


def test_build_initial_plan_produces_bounded_focus_areas():
    from tldw_Server_API.app.core.Research.planner import build_initial_plan

    plan = build_initial_plan(
        query="Assess how local corpus notes and external web sources disagree on GPU memory bandwidth trends",
        source_policy="balanced",
        autonomy_mode="checkpointed",
    )
    assert 3 <= len(plan.focus_areas) <= 7
    assert plan.stop_criteria["min_cited_sections"] >= 1
