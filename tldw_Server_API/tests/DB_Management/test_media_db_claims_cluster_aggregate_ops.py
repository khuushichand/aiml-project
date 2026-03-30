from __future__ import annotations

from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_cluster_aggregate_ops import (
    get_claim_cluster_member_counts,
    get_claim_clusters_by_ids,
    update_claim_clusters_watchlist_counts,
)


pytestmark = pytest.mark.unit


def test_get_claim_clusters_by_ids_returns_empty_list_for_empty_input() -> None:
    assert get_claim_clusters_by_ids(SimpleNamespace(), []) == []


def test_get_claim_cluster_member_counts_returns_empty_dict_for_empty_input() -> None:
    assert get_claim_cluster_member_counts(SimpleNamespace(), []) == {}


def test_get_claim_cluster_member_counts_preserves_tuple_fallback_and_ignores_malformed_rows() -> None:
    class _Cursor:
        def fetchall(self):
            return [
                {"cluster_id": 1, "member_count": 2},
                (2, 5),
                object(),
            ]

    fake_db = SimpleNamespace(
        execute_query=lambda sql, params=None: _Cursor(),
    )

    counts = get_claim_cluster_member_counts(fake_db, [1, 2, 3])

    assert counts == {1: 2, 2: 5}


def test_update_claim_clusters_watchlist_counts_returns_zero_for_empty_input() -> None:
    assert update_claim_clusters_watchlist_counts(SimpleNamespace(), {}) == 0


def test_update_claim_clusters_watchlist_counts_uses_execute_many_and_returns_param_count() -> None:
    execute_many_calls: list[tuple[str, list[tuple[int, int]]]] = []

    def _execute_many(sql: str, params: list[tuple[int, int]]) -> None:
        execute_many_calls.append((sql, params))

    fake_db = SimpleNamespace(execute_many=_execute_many)

    updated = update_claim_clusters_watchlist_counts(fake_db, {9: 4, 12: 6})

    assert updated == 2
    assert execute_many_calls == [
        (
            "UPDATE claim_clusters SET watchlist_count = ? WHERE id = ?",
            [(4, 9), (6, 12)],
        )
    ]
