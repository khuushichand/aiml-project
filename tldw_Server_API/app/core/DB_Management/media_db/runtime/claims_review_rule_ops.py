"""Package-owned claims review rule helpers."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType


def list_claim_review_rules(
    self,
    user_id: str,
    *,
    active_only: bool = False,
) -> list[dict[str, Any]]:
    sql = (
        "SELECT id, user_id, priority, predicate_json, reviewer_id, review_group, active, "
        "created_at, updated_at "
        "FROM claims_review_rules WHERE user_id = ?"
    )
    params: list[Any] = [str(user_id)]
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY priority DESC, id DESC"
    rows = self.execute_query(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def create_claim_review_rule(
    self,
    *,
    user_id: str,
    priority: int,
    predicate_json: str,
    reviewer_id: int | None = None,
    review_group: str | None = None,
    active: bool = True,
) -> dict[str, Any]:
    now = self._get_current_utc_timestamp_str()
    insert_sql = (
        "INSERT INTO claims_review_rules "
        "(user_id, priority, predicate_json, reviewer_id, review_group, active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )
    if self.backend_type == BackendType.POSTGRESQL:
        insert_sql += " RETURNING id"
    cursor = self.execute_query(
        insert_sql,
        (
            str(user_id),
            int(priority),
            str(predicate_json),
            int(reviewer_id) if reviewer_id is not None else None,
            review_group,
            1 if active else 0,
            now,
            now,
        ),
        commit=True,
    )
    if self.backend_type == BackendType.POSTGRESQL:
        row = cursor.fetchone()
        rule_id = int(row["id"]) if row else None
    else:
        rule_id = cursor.lastrowid
    if rule_id is None:
        return {}
    return get_claim_review_rule(self, rule_id)


def get_claim_review_rule(self, rule_id: int) -> dict[str, Any]:
    row = self.execute_query(
        "SELECT id, user_id, priority, predicate_json, reviewer_id, review_group, active, "
        "created_at, updated_at FROM claims_review_rules WHERE id = ?",
        (int(rule_id),),
    ).fetchone()
    return dict(row) if row else {}


def update_claim_review_rule(
    self,
    rule_id: int,
    *,
    priority: int | None = None,
    predicate_json: str | None = None,
    reviewer_id: int | None = None,
    review_group: str | None = None,
    active: bool | None = None,
) -> dict[str, Any]:
    update_parts: list[str] = []
    params: list[Any] = []
    now = self._get_current_utc_timestamp_str()

    if priority is not None:
        update_parts.append("priority = ?")
        params.append(int(priority))
    if predicate_json is not None:
        update_parts.append("predicate_json = ?")
        params.append(str(predicate_json))
    if reviewer_id is not None:
        update_parts.append("reviewer_id = ?")
        params.append(int(reviewer_id))
    if review_group is not None:
        update_parts.append("review_group = ?")
        params.append(str(review_group))
    if active is not None:
        update_parts.append("active = ?")
        params.append(1 if active else 0)

    if not update_parts:
        return get_claim_review_rule(self, int(rule_id))

    update_parts.append("updated_at = ?")
    params.append(now)
    params.append(int(rule_id))

    sql = "UPDATE claims_review_rules SET " + ", ".join(update_parts) + " WHERE id = ?"  # nosec B608
    self.execute_query(sql, tuple(params), commit=True)
    return get_claim_review_rule(self, int(rule_id))


def delete_claim_review_rule(self, rule_id: int) -> None:
    self.execute_query(
        "DELETE FROM claims_review_rules WHERE id = ?",
        (int(rule_id),),
        commit=True,
    )
