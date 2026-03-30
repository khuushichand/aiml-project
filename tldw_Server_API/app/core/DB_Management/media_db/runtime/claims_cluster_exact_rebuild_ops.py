"""Package-owned claims cluster exact rebuild coordinator."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType


def rebuild_claim_clusters_exact(
    self,
    *,
    user_id: str,
    min_size: int = 2,
) -> dict[str, int]:
    """Rebuild clusters by exact normalized claim text."""
    try:
        min_size = int(min_size)
    except (TypeError, ValueError):
        min_size = 2
    min_size = max(1, min_size)

    clusters_created = 0
    claims_assigned = 0

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
                f"UPDATE Claims SET claim_cluster_id = NULL WHERE claim_cluster_id IN ({placeholders})",  # nosec B608
                params,
            )
            self._execute_with_connection(
                conn,
                f"DELETE FROM claim_clusters WHERE id IN ({placeholders})",  # nosec B608
                params,
            )

        rows = self._fetchall_with_connection(
            conn,
            (
                "SELECT c.id, c.claim_text FROM Claims c "
                "JOIN Media m ON c.media_id = m.id "
                "WHERE c.deleted = 0 AND COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?"
            ),
            (str(user_id),),
        )

        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            text = str(row.get("claim_text") or "").strip()
            if not text:
                continue
            normalized_text = " ".join(text.lower().split())
            groups.setdefault(normalized_text, []).append(
                {"id": int(row["id"]), "text": text}
            )

        for claims in groups.values():
            if len(claims) < min_size:
                continue
            representative = claims[0]
            now = self._get_current_utc_timestamp_str()
            insert_sql = (
                "INSERT INTO claim_clusters "
                "(user_id, canonical_claim_text, representative_claim_id, summary, "
                "cluster_version, watchlist_count, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            )
            if self.backend_type == BackendType.POSTGRESQL:
                insert_sql += " RETURNING id"
            cursor = self._execute_with_connection(
                conn,
                insert_sql,
                (
                    str(user_id),
                    representative["text"],
                    representative["id"],
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
            for claim in claims:
                self._execute_with_connection(
                    conn,
                    (
                        "INSERT INTO claim_cluster_membership "
                        "(cluster_id, claim_id, similarity_score, cluster_joined_at) "
                        "VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING"
                    ),
                    (int(cluster_id), int(claim["id"]), 1.0, now),
                )
                self._execute_with_connection(
                    conn,
                    "UPDATE Claims SET claim_cluster_id = ? WHERE id = ?",
                    (int(cluster_id), int(claim["id"])),
                )
                claims_assigned += 1
            self._execute_with_connection(
                conn,
                "UPDATE claim_clusters SET cluster_version = cluster_version + 1, updated_at = ? WHERE id = ?",
                (now, int(cluster_id)),
            )

    return {
        "clusters_created": clusters_created,
        "claims_assigned": claims_assigned,
    }
