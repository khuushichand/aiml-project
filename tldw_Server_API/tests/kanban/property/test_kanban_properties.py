"""Property-based invariants for Kanban DB behavior."""

from __future__ import annotations

import uuid

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st


pytestmark = pytest.mark.unit


@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(card_seeds=st.lists(st.integers(min_value=1, max_value=50_000), min_size=2, max_size=12, unique=True))
def test_card_positions_contiguous_after_reorder(kanban_db, card_seeds):
    """Reordering cards should always produce contiguous 0..N-1 positions."""
    suffix = uuid.uuid4().hex[:10]
    board = kanban_db.create_board(name=f"PBT Board {suffix}", client_id=f"pbt-board-{suffix}")
    lst = kanban_db.create_list(board_id=board["id"], name="PBT List", client_id=f"pbt-list-{suffix}")

    created_ids = []
    for seed in card_seeds:
        card = kanban_db.create_card(
            list_id=lst["id"],
            title=f"PBT card {seed}",
            client_id=f"pbt-card-{suffix}-{seed}",
        )
        created_ids.append(card["id"])

    new_order = list(reversed(created_ids))
    kanban_db.reorder_cards(list_id=lst["id"], card_ids=new_order)

    cards = kanban_db.list_cards(list_id=lst["id"])
    assert [card["id"] for card in cards] == new_order
    assert [card["position"] for card in cards] == list(range(len(cards)))


@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(transitions=st.lists(st.tuples(st.booleans(), st.booleans()), min_size=1, max_size=10))
def test_search_visibility_matches_archive_delete_state(kanban_db, transitions):
    """FTS search visibility should match (not archived and not deleted)."""
    suffix = uuid.uuid4().hex[:10]
    token = f"needle-{suffix}"

    board = kanban_db.create_board(name=f"FTS Board {suffix}", client_id=f"fts-board-{suffix}")
    lst = kanban_db.create_list(board_id=board["id"], name="FTS List", client_id=f"fts-list-{suffix}")
    card = kanban_db.create_card(
        list_id=lst["id"],
        title=f"{token} title",
        description=f"{token} description",
        client_id=f"fts-card-{suffix}",
    )

    current_archived = False
    current_deleted = False

    for archived, deleted in transitions:
        if current_deleted and archived != current_archived:
            kanban_db.restore_card(card_id=card["id"])
            current_deleted = False

        if archived != current_archived:
            kanban_db.archive_card(card_id=card["id"], archive=archived)
            current_archived = archived

        if deleted != current_deleted:
            if deleted:
                assert kanban_db.delete_card(card_id=card["id"], hard_delete=False)
            else:
                kanban_db.restore_card(card_id=card["id"])
            current_deleted = deleted

        results, _total = kanban_db.search_cards(query=token)
        visible = any(result["id"] == card["id"] for result in results)
        assert visible == (not current_archived and not current_deleted)
