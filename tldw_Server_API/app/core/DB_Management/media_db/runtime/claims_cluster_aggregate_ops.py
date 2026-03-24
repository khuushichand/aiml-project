"""Package-owned claims cluster aggregate helpers."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)


_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def get_claim_clusters_by_ids(self, cluster_ids: list[int]) -> list[dict[str, Any]]:
    if not cluster_ids:
        return []
    placeholders = ",".join("?" * len(cluster_ids))
    sql = (
        "SELECT id, canonical_claim_text, updated_at "  # nosec B608
        f"FROM claim_clusters WHERE id IN ({placeholders})"
    )
    rows = self.execute_query(sql, tuple(int(cid) for cid in cluster_ids)).fetchall()
    return [dict(row) for row in rows]


def get_claim_cluster_member_counts(self, cluster_ids: list[int]) -> dict[int, int]:
    if not cluster_ids:
        return {}
    placeholders = ",".join("?" * len(cluster_ids))
    sql = (
        "SELECT cluster_id, COUNT(*) AS member_count "  # nosec B608
        f"FROM claim_cluster_membership WHERE cluster_id IN ({placeholders}) "
        "GROUP BY cluster_id"
    )
    rows = self.execute_query(sql, tuple(int(cid) for cid in cluster_ids)).fetchall()
    counts: dict[int, int] = {}
    for row in rows:
        try:
            cluster_id = int(row["cluster_id"])
            member_count = int(row["member_count"])
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            try:
                cluster_id = int(row[0])
                member_count = int(row[1])
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                continue
        counts[cluster_id] = member_count
    return counts


def update_claim_clusters_watchlist_counts(self, counts: dict[int, int]) -> int:
    if not counts:
        return 0
    params = [(int(count), int(cluster_id)) for cluster_id, count in counts.items()]
    self.execute_many(
        "UPDATE claim_clusters SET watchlist_count = ? WHERE id = ?",
        params,
    )
    return len(params)
