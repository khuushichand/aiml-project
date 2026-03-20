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


def test_build_initial_plan_uses_follow_up_background_to_bias_focus_areas():
    from tldw_Server_API.app.core.Research.planner import build_initial_plan

    plan = build_initial_plan(
        query="What should we research next?",
        source_policy="balanced",
        autonomy_mode="checkpointed",
        follow_up_background={
            "question": "What did the attached research conclude about the council payroll freeze?",
            "key_claims": [
                {
                    "claim_id": "clm_1",
                    "text": "The council payroll freeze remains contested.",
                }
            ],
            "unresolved_questions": ["Did the council approve the payroll freeze?"],
        },
    )

    assert any(
        "council" in focus_area.lower() or "payroll" in focus_area.lower()
        for focus_area in plan.focus_areas
    )
