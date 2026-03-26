"""Package-owned claims cluster assignment rebuild coordinator."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType


def rebuild_claim_clusters_from_assignments(
    self,
    *,
    user_id: str,
    clusters: list[dict[str, Any]],
) -> dict[str, int]:
    """Rebuild clusters from precomputed assignments."""
    clusters_created = 0
    claims_assigned = 0
    now = self._get_current_utc_timestamp_str()

    with self.transaction() as conn:
        cluster_rows = self._fetchall_with_connection(
            conn,
            "SELECT id FROM claim_clusters WHERE user_id = ?",
            (str(user_id),),
        )
        cluster_ids = [int(r["id"]) for r in cluster_rows if r.get("id") is not None]
        if cluster_ids:
            placeholders = ",".join("?" * len(cluster_ids))
            params = tuple(cluster_ids)
            self._execute_with_connection(
                conn,
                f"DELETE FROM claim_cluster_membership WHERE cluster_id IN ({placeholders})",  # nosec B608
                params,
            )
            self._execute_with_connection(
                conn,
                f"DELETE FROM claim_clusters WHERE id IN ({placeholders})",  # nosec B608
                params,
            )

        self._execute_with_connection(
            conn,
            (
                "UPDATE Claims SET claim_cluster_id = NULL "
                "WHERE id IN ("
                "SELECT c.id FROM Claims c "
                "JOIN Media m ON c.media_id = m.id "
                "WHERE COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?"
                ")"
            ),
            (str(user_id),),
        )

        membership_sql = (
            "INSERT INTO claim_cluster_membership "
            "(cluster_id, claim_id, similarity_score, cluster_joined_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING"
        )

        for cluster in clusters:
            canonical_text = str(cluster.get("canonical_claim_text") or "")
            rep_id = cluster.get("representative_claim_id")
            insert_sql = (
                "INSERT INTO claim_clusters "
                "(user_id, canonical_claim_text, representative_claim_id, summary, "
                "cluster_version, watchlist_count, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            )
            if self.backend_type == BackendType.POSTGRESQL:
                insert_sql = (
                    "INSERT INTO claim_clusters "
                    "(user_id, canonical_claim_text, representative_claim_id, summary, "
                    "cluster_version, watchlist_count, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id"
                )
            cursor = self._execute_with_connection(
                conn,
                insert_sql,
                (
                    str(user_id),
                    canonical_text,
                    int(rep_id) if rep_id is not None else None,
                    None,
                    1,
                    0,
                    now,
                    now,
                ),
            )
            if self.backend_type == BackendType.POSTGRESQL:
                inserted = cursor.fetchone()
                cluster_id = inserted["id"] if inserted else None
            else:
                cluster_id = cursor.lastrowid
            if not cluster_id:
                continue
            clusters_created += 1

            members = cluster.get("members") or []
            membership_params: list[tuple[int, int, float | None, str]] = []
            update_params: list[tuple[int, int]] = []
            for member in members:
                claim_id = member.get("claim_id")
                if claim_id is None:
                    continue
                similarity = member.get("similarity")
                membership_params.append(
                    (
                        int(cluster_id),
                        int(claim_id),
                        float(similarity) if similarity is not None else None,
                        now,
                    )
                )
                update_params.append((int(cluster_id), int(claim_id)))
                claims_assigned += 1

            if membership_params:
                self.execute_many(
                    membership_sql,
                    membership_params,
                    connection=conn,
                )
            if update_params:
                self.execute_many(
                    "UPDATE Claims SET claim_cluster_id = ? WHERE id = ?",
                    update_params,
                    connection=conn,
                )

    return {
        "clusters_created": clusters_created,
        "claims_assigned": claims_assigned,
    }
