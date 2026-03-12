from __future__ import annotations

import pytest

from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB


pytestmark = pytest.mark.unit


def test_companion_goal_round_trip_preserves_origin_and_progress_mode(tmp_path) -> None:
    db = PersonalizationDB(str(tmp_path / "personalization.db"))

    goal_id = db.create_companion_goal(
        user_id="1",
        title="Follow up on backlog",
        description=None,
        goal_type="manual",
        config={},
        progress={},
        status="active",
        origin_kind="manual",
        progress_mode="computed",
        derivation_key=None,
        evidence=[{"event_id": "evt-1"}],
    )

    goal = db.update_companion_goal(goal_id, "1")

    assert goal is not None
    assert goal["origin_kind"] == "manual"
    assert goal["progress_mode"] == "computed"
    assert goal["derivation_key"] is None
    assert goal["evidence"] == [{"event_id": "evt-1"}]
