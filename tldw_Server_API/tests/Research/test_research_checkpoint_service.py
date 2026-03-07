import pytest


pytestmark = pytest.mark.unit


def test_checkpoint_patch_replaces_focus_areas_without_dropping_other_keys():
    from tldw_Server_API.app.core.Research.checkpoint_service import apply_checkpoint_patch

    merged = apply_checkpoint_patch(
        proposed_payload={"focus_areas": ["background"], "source_policy": "balanced"},
        patch_payload={"focus_areas": ["background", "contradictions"]},
    )
    assert merged["source_policy"] == "balanced"
    assert merged["focus_areas"][1] == "contradictions"
